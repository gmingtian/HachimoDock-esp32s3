//! S3 removes builtin games whose primary controls need unavailable hardware.
pub(crate) fn allowed(runtime:&str,id:&str)->bool {
    if runtime!="esp-s3" { return true; }
    let policy:serde_json::Value=serde_json::from_str(include_str!("../../../firmware/s3/component-policy.json")).expect("checked S3 policy");
    !policy["unsupportedBuiltins"].as_array().is_some_and(|items|items.iter().any(|item|item.as_str()==Some(id)))
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn s3_three_key_policy_preserves_playable_games_custom_ids_and_p4() {
        for id in ["snake-turn","two-key-pong","flappy-bird","custom-game"] { assert!(allowed("esp-s3",id)); }
        for id in ["block-combo","fresh-fruit-slice","cloud-hop","bloomfrog_companion"] {
            assert!(!allowed("esp-s3",id)); assert!(allowed("esp-p4",id));
        }
    }
}
