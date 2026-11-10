//! Match the session bus ID and the same agent's rollout ID at the USB boundary.
pub(crate) fn same_session(agent: &str, bound: &str, incoming: &str) -> bool {
    if agent.is_empty() || bound.is_empty() || incoming.is_empty() {
        return false;
    }
    let short_id = |id: &str| {
        id.strip_prefix(agent)
            .and_then(|rest| rest.strip_prefix(':'))
            .unwrap_or(id)
            .to_owned()
    };
    let bound = short_id(bound);
    !bound.is_empty() && bound == short_id(incoming)
}

#[cfg(test)]
mod tests {
    use super::same_session;

    #[test]
    fn codex_rollout_prefix_matches_bus_session() {
        assert!(same_session("codex", "thread-a", "codex:thread-a"));
        assert!(same_session("codex", "codex:thread-a", "thread-a"));
    }

    #[test]
    fn prefixed_ids_also_match_each_other() {
        assert!(same_session("codex", "codex:thread-a", "codex:thread-a"));
        assert!(!same_session("codex", "codex:thread-a", "codex:thread-b"));
    }

    #[test]
    fn different_sessions_and_foreign_prefixes_do_not_match() {
        assert!(!same_session("codex", "thread-a", "codex:thread-b"));
        assert!(!same_session("codex", "thread-a", "claude-code:thread-a"));
        assert!(!same_session("codex", "thread-a", "codex:codex:thread-a"));
        assert!(!same_session("codex", "claude-code:thread-a", "thread-a"));
    }

    #[test]
    fn blank_session_never_matches() {
        for id in ["", "codex:"] {
            assert!(!same_session("codex", "", id));
            assert!(!same_session("codex", id, ""));
            assert!(!same_session("codex", id, id));
        }
        assert!(!same_session("", "thread-a", "thread-a"));
    }

    #[test]
    fn exact_ids_and_other_agents_keep_their_namespace() {
        assert!(same_session("codex", "thread-a", "thread-a"));
        assert!(same_session("claude-code", "thread-a", "claude-code:thread-a"));
        assert!(same_session("deepseek-harness", "local:thread-a", "local:thread-a"));
        assert!(!same_session("deepseek-harness", "local:thread-a", "thread-a"));
    }
}
