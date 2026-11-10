//! Modem-line policy for runtime discovery, never a flashing/reset sequence.

pub(super) fn assert_runtime_modem_lines(platform: &str, usb_id: Option<(u16, u16)>) -> bool {
    platform == "linux" && usb_id == Some((0x303a, 0x1001))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn linux_native_usb_jtag_stays_in_the_working_runtime_line_state() {
        assert!(assert_runtime_modem_lines("linux", Some((0x303a, 0x1001))));
    }

    #[test]
    fn windows_macos_and_external_uart_keep_the_existing_line_state() {
        for platform in ["windows", "macos"] {
            assert!(!assert_runtime_modem_lines(platform, Some((0x303a, 0x1001))));
        }
        for id in [None, Some((0x10c4, 0xea60)), Some((0x1a86, 0x55d3)),
                   Some((0x303a, 0x4001)), Some((0x0403, 0x6001))] {
            assert!(!assert_runtime_modem_lines("linux", id));
        }
    }
}
