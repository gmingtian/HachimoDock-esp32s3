//! TLS byte-stream adapter. One I/O thread owns the TLS state; consumers use
//! bounded Read/Write handles so audio reception never waits on a writer lock.
use rustls::pki_types::{pem::PemObject, CertificateDer, ServerName};
use rustls::{ClientConfig, ClientConnection, RootCertStore};
use serde::{Deserialize, Serialize};
use std::io::{self, Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::sync::{atomic::{AtomicBool, Ordering}, mpsc, Arc};
use std::thread;
use std::time::{Duration, Instant};

const IO_SLICE: Duration = Duration::from_millis(10);
const DEADLINE: Duration = Duration::from_secs(5);
const WRITE_DEADLINE: Duration = Duration::from_secs(1);
const CHUNK: usize = 16 * 1024;

// Deliberately no Debug: the authentication token must never enter diagnostics.
#[derive(Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct WifiIdentity {
    pub board_device_id: String,
    pub hostname: String,
    pub certificate_pem: String,
    pub token: String,
}

struct WriteJob {
    bytes: Vec<u8>,
    done: mpsc::SyncSender<io::Result<usize>>,
}

pub(crate) struct WifiReader {
    incoming: mpsc::Receiver<Vec<u8>>,
    pending: Vec<u8>,
    offset: usize,
    cancel: Arc<AtomicBool>,
}
pub(crate) struct WifiWriter {
    outgoing: mpsc::SyncSender<WriteJob>,
    cancel: Arc<AtomicBool>,
}
pub(crate) struct WifiIo {
    pub reader: WifiReader,
    pub writer: WifiWriter,
    pub cancel: Arc<AtomicBool>,
}

// write_all retries Interrupted forever; cancellation must be terminal.
fn interrupted() -> io::Error { io::Error::new(io::ErrorKind::ConnectionAborted, "device connection cancelled") }
fn transient(error: &io::Error) -> bool {
    matches!(error.kind(), io::ErrorKind::WouldBlock | io::ErrorKind::TimedOut | io::ErrorKind::Interrupted)
}

impl Read for WifiReader {
    fn read(&mut self, out: &mut [u8]) -> io::Result<usize> {
        if self.cancel.load(Ordering::Acquire) { return Err(interrupted()); }
        if out.is_empty() { return Ok(0); }
        if self.offset == self.pending.len() {
            self.pending = match self.incoming.recv_timeout(Duration::from_millis(100)) {
                Ok(bytes) => bytes,
                Err(mpsc::RecvTimeoutError::Timeout) => return Err(io::ErrorKind::TimedOut.into()),
                Err(mpsc::RecvTimeoutError::Disconnected) => return Ok(0),
            };
            self.offset = 0;
        }
        let count = out.len().min(self.pending.len() - self.offset);
        out[..count].copy_from_slice(&self.pending[self.offset..self.offset + count]);
        self.offset += count;
        Ok(count)
    }
}

impl Write for WifiWriter {
    fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
        if self.cancel.load(Ordering::Acquire) { return Err(interrupted()); }
        if bytes.is_empty() { return Ok(0); }
        let count = bytes.len().min(CHUNK);
        let (done, result) = mpsc::sync_channel(1);
        let job = WriteJob { bytes: bytes[..count].to_vec(), done };
        self.outgoing.try_send(job).map_err(|_| {
            self.cancel.store(true, Ordering::Release);
            io::Error::new(io::ErrorKind::BrokenPipe, "Wi-Fi send queue unavailable")
        })?;
        let deadline = Instant::now() + WRITE_DEADLINE;
        loop {
            if self.cancel.load(Ordering::Acquire) { return Err(interrupted()); }
            match result.recv_timeout(IO_SLICE) {
                Ok(result) => return result,
                Err(mpsc::RecvTimeoutError::Disconnected) => return Err(io::ErrorKind::BrokenPipe.into()),
                Err(mpsc::RecvTimeoutError::Timeout) if Instant::now() >= deadline => {
                    self.cancel.store(true, Ordering::Release);
                    return Err(io::Error::new(io::ErrorKind::TimedOut, "Wi-Fi send deadline exceeded"));
                }
                Err(_) => (),
            }
        }
    }
    // Every successful write has already drained encrypted bytes to the socket.
    fn flush(&mut self) -> io::Result<()> {
        if self.cancel.load(Ordering::Acquire) { Err(interrupted()) } else { Ok(()) }
    }
}
impl Drop for WifiWriter {
    fn drop(&mut self) { self.cancel.store(true, Ordering::Release); }
}

pub(crate) fn read_json_line<R: Read>(reader: &mut R, limit: usize, deadline: Instant) -> Result<serde_json::Value, String> {
    let mut bytes = Vec::new();
    let mut byte = [0u8; 1];
    while Instant::now() < deadline {
        match reader.read(&mut byte) {
            Ok(0) => return Err("Wi-Fi connection closed".into()),
            Ok(_) if byte[0] == b'\n' => return serde_json::from_slice(&bytes).map_err(|_| "Invalid Wi-Fi protocol frame".into()),
            Ok(_) if bytes.len() >= limit => return Err("Wi-Fi protocol frame exceeds size limit".into()),
            Ok(_) => bytes.push(byte[0]),
            Err(error) if transient(&error) => (),
            Err(_) => return Err("Wi-Fi protocol read failed".into()),
        }
    }
    Err("Wi-Fi protocol response timed out".into())
}

fn tls_config(identity: &WifiIdentity) -> Result<Arc<ClientConfig>, String> {
    let certificate = CertificateDer::from_pem_slice(identity.certificate_pem.as_bytes())
        .map_err(|_| "设备证书格式无效，请通过 USB 重新绑定")?;
    let mut roots = RootCertStore::empty();
    roots.add(certificate).map_err(|_| "设备证书无效")?;
    let config = ClientConfig::builder_with_provider(Arc::new(rustls::crypto::ring::default_provider()))
        .with_safe_default_protocol_versions().map_err(|_| "TLS 配置失败")?
        .with_root_certificates(roots).with_no_client_auth();
    Ok(Arc::new(config))
}

pub(crate) fn connect(identity: &WifiIdentity, address: SocketAddr, desktop_id: &str, takeover: bool) -> Result<WifiIo, String> {
    let config = tls_config(identity)?;
    let server_name = ServerName::try_from(identity.hostname.clone()).map_err(|_| "设备主机名无效")?;
    let mut tls = ClientConnection::new(config, server_name).map_err(|_| "TLS 初始化失败")?;
    let mut socket = TcpStream::connect_timeout(&address, DEADLINE).map_err(|_| "无法连接设备，请检查局域网与设备 IP")?;
    socket.set_nodelay(true).map_err(|_| "Wi-Fi 连接配置失败")?;
    socket.set_read_timeout(Some(IO_SLICE)).map_err(|_| "Wi-Fi 连接配置失败")?;
    socket.set_write_timeout(Some(WRITE_DEADLINE)).map_err(|_| "Wi-Fi 连接配置失败")?;
    let deadline = Instant::now() + DEADLINE;
    while tls.is_handshaking() {
        if Instant::now() >= deadline { return Err("设备 TLS 握手超时".into()); }
        match tls.complete_io(&mut socket) {
            Ok(_) => (),
            Err(error) if transient(&error) => (),
            Err(_) => return Err("设备 TLS 身份校验失败，请通过 USB 核对绑定".into()),
        }
    }
    let request_id = format!("wifi-auth-{}", uuid::Uuid::new_v4());
    let auth = serde_json::json!({"topic":"wifi/auth","payload":{
        "requestId":request_id,"token":identity.token,"desktopDeviceId":desktop_id,
        "expectedBoardDeviceId":identity.board_device_id,"takeover":takeover
    }});
    {
        let mut stream = rustls::Stream::new(&mut tls, &mut socket);
        stream.write_all(format!("{auth}\n").as_bytes()).map_err(|_| "Wi-Fi 认证发送失败")?;
        stream.flush().map_err(|_| "Wi-Fi 认证发送失败")?;
        let response = read_json_line(&mut stream, 32768, Instant::now()+DEADLINE)?;
        if response["topic"] != "wifi/auth" || response["payload"]["requestId"] != request_id
            || response["payload"]["ok"] != true || response["payload"]["boardDeviceId"] != identity.board_device_id {
            return Err("无线认证失败或设备正在使用，请检查绑定并停止当前操作".into());
        }
    }
    socket.set_nonblocking(true).map_err(|_| "Wi-Fi 连接配置失败")?;
    let (output, jobs) = mpsc::sync_channel(8); // <= 8 * 16KiB, plus one in-flight chunk.
    let (received, input) = mpsc::sync_channel(8);
    let cancel = Arc::new(AtomicBool::new(false));
    let worker_cancel = Arc::clone(&cancel);
    thread::spawn(move || { let _ = pump(tls, socket, jobs, received, worker_cancel); });
    Ok(WifiIo {
        reader: WifiReader { incoming: input, pending: Vec::new(), offset: 0, cancel: Arc::clone(&cancel) },
        writer: WifiWriter { outgoing: output, cancel: Arc::clone(&cancel) }, cancel,
    })
}

fn receive(tls: &mut ClientConnection, socket: &mut TcpStream, output: &mpsc::SyncSender<Vec<u8>>) -> io::Result<bool> {
    let mut eof = false;
    match tls.read_tls(socket) {
        Ok(0) => eof = true,
        Ok(_) => { tls.process_new_packets().map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "TLS packet rejected"))?; }
        Err(error) if transient(&error) => (),
        Err(error) => return Err(error),
    }
    let mut buffer = [0u8; CHUNK];
    loop {
        match tls.reader().read(&mut buffer) {
            Ok(0) => return Ok(false),
            Ok(count) => output.try_send(buffer[..count].to_vec()).map_err(|_| io::Error::new(io::ErrorKind::OutOfMemory, "Wi-Fi receive queue full"))?,
            Err(error) if error.kind() == io::ErrorKind::WouldBlock => break,
            Err(error) if error.kind() == io::ErrorKind::UnexpectedEof => return Ok(false),
            Err(error) => return Err(error),
        }
    }
    Ok(!eof)
}

fn pump(mut tls: ClientConnection, mut socket: TcpStream, jobs: mpsc::Receiver<WriteJob>, received: mpsc::SyncSender<Vec<u8>>, cancel: Arc<AtomicBool>) -> io::Result<()> {
    while !cancel.load(Ordering::Acquire) {
        // A successful handshake can already have buffered application bytes.
        if !receive(&mut tls, &mut socket, &received)? { return Ok(()); }
        match jobs.try_recv() {
            Ok(job) => {
                let result = (|| {
                    tls.writer().write_all(&job.bytes)?;
                    let deadline = Instant::now() + WRITE_DEADLINE;
                    while tls.wants_write() {
                        if cancel.load(Ordering::Acquire) { return Err(interrupted()); }
                        if Instant::now() >= deadline { return Err(io::ErrorKind::TimedOut.into()); }
                        match tls.write_tls(&mut socket) {
                            Ok(0) => return Err(io::ErrorKind::WriteZero.into()),
                            Ok(_) => (),
                            Err(error) if transient(&error) => {
                                if !receive(&mut tls, &mut socket, &received)? { return Err(io::ErrorKind::BrokenPipe.into()); }
                                thread::sleep(Duration::from_millis(1));
                            }
                            Err(error) => return Err(error),
                        }
                    }
                    Ok(job.bytes.len())
                })();
                let failed = result.is_err();
                let _ = job.done.send(result);
                if failed { return Err(io::ErrorKind::BrokenPipe.into()); }
            }
            Err(mpsc::TryRecvError::Disconnected) => return Ok(()),
            Err(mpsc::TryRecvError::Empty) => thread::sleep(Duration::from_millis(1)),
        }
    }
    Ok(())
}

#[cfg(test)]
#[path = "wifi_transport_tests.rs"]
mod tests;
