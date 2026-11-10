use super::UsbFollowScope;
use serde_json::json;

fn bound() -> UsbFollowScope {
    UsbFollowScope {
        generation: 1,
        board: "s3-test".into(),
        agent: "codex".into(),
        session: Some("thread-a".into()),
        submitted: true,
    }
}

#[test]
fn rollout_alias_allows_activity_and_completion_on_the_bound_wire() {
    let scope = bound();
    for state in ["working", "speaking", "done", "idle"] {
        assert!(scope.allows("state/codex", &json!({"sessionId":"codex:thread-a","state":state})));
        assert!(scope.allows("state/active", &json!({"source":"codex","sessionId":"codex:thread-a","state":state})));
    }
    assert!(scope.allows("speech/text", &json!({"source":"codex","sessionId":"codex:thread-a"})));
}

#[test]
fn wire_admission_rejects_other_agents_sessions_and_unsubmitted_follow() {
    let mut scope = bound();
    for id in ["thread-b", "codex:thread-b", "claude-code:thread-a", "codex:", ""] {
        assert!(!scope.allows("state/codex", &json!({"sessionId":id})));
    }
    assert!(!scope.allows("state/claude-code", &json!({"sessionId":"thread-a"})));
    assert!(!scope.allows("speech/text", &json!({"sessionId":"thread-a"})));
    scope.submitted = false;
    assert!(!scope.allows("state/codex", &json!({"sessionId":"codex:thread-a"})));
}
