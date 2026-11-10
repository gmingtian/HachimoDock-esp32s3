//! Offline, bounded video review frames. Never send URLs to a decoder or use
//! WebView canvas readback, which can produce noise on Linux WebKitGTK.
use serde::Serialize;
use base64::Engine;
use std::{fs, io::Cursor, path::Path, process::{Command, Stdio}, time::{Duration, Instant}};

const INVALID: &str = "VIDEO_INSPECTION_INPUT_INVALID";
const DECODE: &str = "VIDEO_INSPECTION_DECODE_ERROR";
const DIMENSIONS: &str = "VIDEO_INSPECTION_DIMENSIONS_INVALID";
const MAX_BYTES: usize = 100 * 1024 * 1024;

pub(crate) fn decoder_path() -> String {
    // Discovery must not launch unbounded version/encoder probes. Decoding the
    // actual owned clip below is the capability check, under the same deadline.
    if let Some(path) = std::env::var_os("PET_MANAGER_BUNDLED_FFMPEG") {
        return Path::new(&path).to_string_lossy().into_owned();
    }
    if let Ok(executable) = std::env::current_exe() {
        #[cfg(target_os = "macos")]
        if let Some(contents) = executable.parent().and_then(Path::parent) {
            let path = contents.join("Resources/tools/ffmpeg");
            if path.is_file() { return path.to_string_lossy().into_owned(); }
        }
        #[cfg(windows)]
        if let Some(dir) = executable.parent() {
            let path = dir.join("tools/ffmpeg.exe");
            if path.is_file() { return path.to_string_lossy().into_owned(); }
        }
        #[cfg(not(any(windows, target_os = "macos")))]
        let _ = executable;
    }
    for dir in std::env::split_paths(&std::env::var_os("PATH").unwrap_or_default()) {
        let path = dir.join(if cfg!(windows) { "ffmpeg.exe" } else { "ffmpeg" });
        if path.is_file() { return path.to_string_lossy().into_owned(); }
    }
    for path in ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"] {
        if Path::new(path).is_file() { return path.into(); }
    }
    "ffmpeg".into()
}

#[derive(Debug, Serialize)]
pub(crate) struct Inspection {
    duration: f64,
    width: u32,
    height: u32,
    frames: Vec<String>,
    decoder: &'static str,
}

fn command(ffmpeg: &str) -> Command {
    let mut command = Command::new(ffmpeg);
    #[cfg(windows)] {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000); // CREATE_NO_WINDOW
    }
    command.args(["-hide_banner", "-nostdin", "-nostats"]);
    command
}

// Disk-backed diagnostics avoid pipe deadlock; never return raw decoder stderr
// to the UI. Every child is reaped even on timeout, overflow or I/O failure.
fn run(command: &mut Command, deadline: Instant) -> Result<Vec<u8>, String> {
    let mut log = tempfile::tempfile().map_err(|_| DECODE)?;
    let mut child = command.stdin(Stdio::null()).stdout(Stdio::null())
        .stderr(log.try_clone().map_err(|_| DECODE)?).spawn().map_err(|_| DECODE)?;
    let result = loop {
        if Instant::now() >= deadline || log.metadata().map(|m| m.len() > 128 * 1024).unwrap_or(true) {
            break Err(DECODE.to_string());
        }
        match child.try_wait() {
            Ok(Some(status)) => break if status.success() { Ok(()) } else { Err(DECODE.to_string()) },
            Ok(None) => std::thread::sleep(Duration::from_millis(15)),
            Err(_) => break Err(DECODE.to_string()),
        }
    };
    if result.is_err() { let _ = child.kill(); }
    let _ = child.wait();
    result?;
    use std::io::{Read, Seek, SeekFrom};
    log.seek(SeekFrom::Start(0)).map_err(|_| DECODE)?;
    let mut bytes = Vec::new();
    log.take(128 * 1024 + 1).read_to_end(&mut bytes).map_err(|_| DECODE)?;
    if bytes.len() > 128 * 1024 { return Err(DECODE.into()); }
    Ok(bytes)
}

fn metadata(log: &[u8]) -> Result<(f64, u32, u32), String> {
    let text = String::from_utf8_lossy(log);
    let duration = text.lines().filter_map(|line| line.split_once("Duration: "))
        .find_map(|(_, rest)| {
            let value = rest.split(',').next()?;
            let parts: Vec<f64> = value.trim().split(':').map(str::parse).collect::<Result<_, _>>().ok()?;
            (parts.len() == 3).then(|| parts[0]*3600.0 + parts[1]*60.0 + parts[2])
        }).ok_or(DIMENSIONS)?;
    let (width, height) = text.lines().filter(|line| line.contains("Parsed_showinfo"))
        .flat_map(str::split_whitespace).filter_map(|part| part.strip_prefix("s:"))
        .find_map(|part| {
            let (w, h) = part.split_once('x')?;
            Some((w.parse::<u32>().ok()?, h.parse::<u32>().ok()?))
        }).ok_or(DIMENSIONS)?;
    if !duration.is_finite() || !(1.0..=30.0).contains(&duration)
        || width < 128 || height < 128 || u64::from(width)*u64::from(height) > 16_777_216 {
        return Err(DIMENSIONS.into());
    }
    if (384.0 * f64::from(height) / f64::from(width)).round() > 1536.0 {
        return Err("VIDEO_INSPECTION_ASPECT_INVALID".into());
    }
    Ok((duration, width, height))
}

fn local_input(command: &mut Command, input: &Path) {
    // mov only + no external data references: uploaded bytes cannot become a
    // playlist, network URL, or request to open arbitrary files on the host.
    command.args(["-threads", "2", "-max_pixels", "16777216", "-protocol_whitelist", "file,pipe",
        "-f", "mov", "-enable_drefs", "0", "-use_absolute_path", "0", "-i"]).arg(input);
    command.args(["-map", "0:v:0", "-an", "-sn", "-dn"]);
}

fn frame_step(log: &[u8]) -> f64 {
    String::from_utf8_lossy(log).lines().filter(|line| line.contains("Parsed_showinfo"))
        .filter_map(|line| line.split_once("frame_rate:"))
        .find_map(|(_, rate)| {
            let (n, d) = rate.trim().split_whitespace().next()?.split_once('/')?;
            let step = d.parse::<f64>().ok()? / n.parse::<f64>().ok()?;
            (step.is_finite() && step > 0.0).then_some(step.clamp(0.001, 30.0))
        }).unwrap_or(0.1)
}

pub(crate) fn inspect_with_ffmpeg(bytes: &[u8], ffmpeg: &str) -> Result<Inspection, String> {
    if bytes.is_empty() || bytes.len() > MAX_BYTES { return Err(INVALID.into()); }
    let dir = tempfile::tempdir().map_err(|_| DECODE)?;
    let input = dir.path().join("input.mp4");
    fs::write(&input, bytes).map_err(|_| DECODE)?;
    let deadline = Instant::now() + Duration::from_secs(45);
    let mut probe = command(ffmpeg);
    probe.args(["-loglevel", "info"]);
    local_input(&mut probe, &input);
    probe.args(["-vf", "showinfo", "-frames:v", "1", "-f", "null", "-"]);
    let log = run(&mut probe, deadline)?;
    let (duration, width, height) = metadata(&log)?;
    let frame_step = frame_step(&log);
    let mut frames = Vec::with_capacity(3);
    for (index, position) in [0.02, 0.5, 0.98].into_iter().enumerate() {
        let output = dir.path().join(format!("frame-{index}.png"));
        let mut decode = command(ffmpeg);
        // A container ends after its last frame's presentation timestamp. Do
        // not seek into that final frame's trailing duration (no output frame).
        let timestamp = (duration * position).min((duration - frame_step - 0.001).max(0.0));
        decode.args(["-loglevel", "error", "-ss", &format!("{timestamp:.6}")]);
        local_input(&mut decode, &input);
        decode.args(["-vf", "scale=384:-1", "-frames:v", "1", "-threads", "1", "-fs", "4194304", "-y"]).arg(&output);
        run(&mut decode, deadline)?;
        if fs::metadata(&output).map_err(|_| DECODE)?.len() > 4 * 1024 * 1024 { return Err(DECODE.into()); }
        let image = image::open(&output).map_err(|_| DECODE)?.to_rgb8();
        if image.width() != 384 || image.height() == 0 || image.height() > 1536 { return Err(DIMENSIONS.into()); }
        let visible = image.pixels().filter(|p| p.0.iter().any(|c| *c > 20)).count();
        if visible as f64 / f64::from(image.width() * image.height()) < 0.001 {
            return Err("VIDEO_INSPECTION_BLACK_FRAME".into());
        }
        let mut jpeg = Cursor::new(Vec::new());
        image::codecs::jpeg::JpegEncoder::new_with_quality(&mut jpeg, 80).encode_image(&image).map_err(|_| DECODE)?;
        frames.push(format!("data:image/jpeg;base64,{}", base64::engine::general_purpose::STANDARD.encode(jpeg.into_inner())));
    }
    Ok(Inspection { duration, width, height, frames, decoder: "ffmpeg-v1" })
}

#[cfg(test)]
mod tests {
    use super::*;
    use base64::Engine;
    use std::process::Command;

    fn fixture(color: &str) -> Option<(tempfile::TempDir, Vec<u8>, String)> {
        let ffmpeg = std::env::var("PET_MANAGER_VIDEO_TEST_FFMPEG").ok()?;
        let dir = tempfile::tempdir().unwrap();
        let file = dir.path().join("input.mp4");
        let status = Command::new(&ffmpeg).args(["-v", "error", "-nostdin", "-f", "lavfi", "-i", color,
            // The reviewed desktop decoder is LGPL-only; these local MP4
            // fixtures must not require the separate GPL x264 encoder helper.
            "-c:v", "mpeg4", "-pix_fmt", "yuv420p", "-y"]).arg(&file).status().unwrap();
        assert!(status.success());
        let bytes = std::fs::read(file).unwrap();
        Some((dir, bytes, ffmpeg))
    }

    #[test]
    fn native_frames_are_decoded_and_distinct_without_webview() {
        let Some((_dir, bytes, ffmpeg)) = fixture("testsrc2=size=320x240:rate=15:duration=2") else { return; };
        let result = inspect_with_ffmpeg(&bytes, &ffmpeg).unwrap();
        assert_eq!((result.width, result.height), (320, 240));
        assert!((result.duration - 2.0).abs() < 0.05);
        assert_eq!(result.decoder, "ffmpeg-v1");
        assert_eq!(result.frames.len(), 3);
        assert_ne!(result.frames[0], result.frames[1]);
        assert_ne!(result.frames[1], result.frames[2]);
        for frame in result.frames {
            let bytes = base64::engine::general_purpose::STANDARD.decode(frame.strip_prefix("data:image/jpeg;base64,").unwrap()).unwrap();
            let image = image::load_from_memory(&bytes).unwrap();
            assert_eq!((image.width(), image.height()), (384, 288));
        }
    }

    #[test]
    fn black_video_is_rejected_in_native_decoder() {
        let Some((_dir, bytes, ffmpeg)) = fixture("color=black:size=320x240:rate=15:duration=2") else { return; };
        assert_eq!(inspect_with_ffmpeg(&bytes, &ffmpeg).unwrap_err(), "VIDEO_INSPECTION_BLACK_FRAME");
    }

    #[test]
    fn native_input_limit_is_checked_before_starting_process() {
        assert_eq!(inspect_with_ffmpeg(&[], "never-run").unwrap_err(), "VIDEO_INSPECTION_INPUT_INVALID");
        assert_eq!(inspect_with_ffmpeg(&vec![0; 100*1024*1024+1], "never-run").unwrap_err(), "VIDEO_INSPECTION_INPUT_INVALID");
    }

    #[test]
    fn invalid_media_cannot_fall_through_or_leak_decoder_errors() {
        let Some(ffmpeg) = std::env::var("PET_MANAGER_VIDEO_TEST_FFMPEG").ok() else { return; };
        let error = inspect_with_ffmpeg(b"https://private.example/signed", &ffmpeg).unwrap_err();
        assert_eq!(error, "VIDEO_INSPECTION_DECODE_ERROR");
    }

    #[test]
    fn final_seek_accepts_low_framerate_video_without_seeking_past_last_frame() {
        let Some((_dir, bytes, ffmpeg)) = fixture("color=white:size=320x240:rate=1:duration=2") else { return; };
        assert_eq!(inspect_with_ffmpeg(&bytes, &ffmpeg).unwrap().frames.len(), 3);
    }

    #[test]
    fn metadata_limits_reject_duration_and_geometry_without_a_review_request() {
        for (duration, size) in [("00:00:00.99", "320x240"), ("00:00:30.01", "320x240"),
            ("00:00:02.00", "127x240"), ("00:00:02.00", "8192x8192"), ("00:00:02.00", "128x1024")] {
            let log = format!("Duration: {duration}, start: 0\n[Parsed_showinfo_0] s:{size}\n");
            assert!(metadata(log.as_bytes()).is_err());
        }
    }

    #[test]
    fn decoder_accepts_only_local_mov_without_external_references() {
        let mut command = command("ffmpeg");
        local_input(&mut command, Path::new("owned-input.mp4"));
        let args: Vec<_> = command.get_args().map(|s| s.to_string_lossy().into_owned()).collect();
        for pair in [["-protocol_whitelist", "file,pipe"], ["-f", "mov"], ["-enable_drefs", "0"], ["-use_absolute_path", "0"]] {
            assert!(args.windows(2).any(|a| a == pair));
        }
    }

    #[cfg(unix)]
    #[test]
    fn decoder_child_is_killed_and_reaped_at_deadline() {
        let start = Instant::now();
        let mut command = Command::new("sh");
        command.args(["-c", "exec sleep 10"]);
        assert!(run(&mut command, start + Duration::from_millis(30)).is_err());
        assert!(start.elapsed() < Duration::from_secs(2));
    }
}
