//! Connection priority depends on the active/actual transport, not its preference.
pub(crate) fn update_reconnect_transport(actual: &str) -> &'static str {
    if actual == "wifi" { "wifi" } else { "usb" }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn wifi_preference_cannot_redirect_a_fallback_usb_update() {
        assert_eq!(update_reconnect_transport("usb"), "usb");
        assert_eq!(update_reconnect_transport("wifi"), "wifi");
    }
}
