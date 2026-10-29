# S3 native home UI review

Scope: latest 240×240 home/session rendering, native overlay guards, menu localization, button-label parsing/action-label lookup, and their two focused tests. Read-only inspection; no firmware flashing, credential access, repository edits, or broad test reruns.

## Strengths

- Native session count is clamped to the 8-item runtime bound; every selected item is included in the maximum 3-card window. The selected 68px card has two 19px body rows, and the art/card geometry stays within the 240px framebuffer.
- Wrapping advances by complete UTF-8 codepoints and guarantees progress even for a too-wide first character. Body paging resets when text changes. All new fixed Chinese labels fit the native row widths.
- The `native_home` flag is always false for P4, preserving the old voice overlay, bubble, session queue, connection banner and rotate calls. Action-label parsing is bounded, labels are presentation-only, and execution retains the original action IDs under the runtime lock.

## Critical

None found within this scope.

## Important

1. **Realtime capture can be stopped by an ignored PTT release.** `firmware/s3/pet_s3_input_menu.inc:151-158` handles VOICE_START/VOICE_END before its conversation ownership branch at line 201. When realtime capture is already running, start fails as busy; release still unconditionally calls `pet_p4_audio_capture_stop()`. That clears the shared capture request (`firmware/main/pet_p4_audio.c:1014-1017`), so the live conversation stops receiving microphone chunks while its conversation state remains active. P4 deliberately ignores PTT while realtime owns input (`firmware/main/pet_p4_input.c:1344-1359`). This defect is in the earlier S3 adapter rather than the latest localization delta, but it violates this feature's required runtime semantics. Move realtime ownership ahead of PTT handling and ignore both hold edges during realtime mode. A production-function C proof in `/tmp/hachimo-native-ui-ptt-proof.c` reproduced start→busy / release→capture stopped, with the conversation check never reached.

2. **New recording prompt promises an immediate send that does not occur.** `firmware/s3/pet_s3_renderer_ui.inc:136` shows `松开确认键发送`. Original device PTT finalization writes a draft and sets `draft_ready`; a later `page_enter` event confirms submission (`pc/src-tauri/src/lib.rs:1427-1438`, `1450-1490`; also documented by `pc/src/DeviceDashboard.jsx:126`). With a queued session this prompt makes the user believe a draft has already been sent. Use an accurate label such as `松开完成录音` or `松开转为文字`; keep the existing confirmation semantics.

## Assessment

**Ready: with fixes above.** No additional memory-safety, session-window, lifecycle, or P4 behavior regression was found in the reviewed native UI paths. Existing supplied UI/action harness results were inspected; the review added only the small realtime/PTT proof, not a full suite rerun. Physical font legibility, panel colors and microphone behavior remain outside this source review.

## Narrow reinspection

The two original findings have been addressed: VOICE_START/VOICE_END now return before audio calls when realtime owns input; the prompt is `松开完成录音`. The native `对话回看` heading also restores the historical-caption distinction. The new `test_confirm_hold_cannot_stop_realtime_capture` passed via direct Python function invocation, compiling/running its production-prefix C harness with UBSan (system Python has no pytest module).

**Remaining Important edge discovered during reinspection:** when ordinary PTT begins first and realtime takes over before the physical confirm release, `session_voice_active` is already true. The new realtime early return preserves capture correctly but never clears that flag. `s3_native_home` at line 104 currently treats that flag as voice feedback even during realtime, so it keeps showing `正在录音` / `松开完成录音` in place of realtime captions; the stale flag can persist after the conversation ends. This takeover is supported by the existing `pet_p4_audio_conversation_set` implementation. Clear the PTT feedback flag when ignoring its hold edges during realtime, and gate native recording feedback with `!realtime`. `/tmp/hachimo-native-ui-takeover-proof.c` confirmed the exact stale-flag sequence using the current production prefix. Final signoff remains **with this narrow fix**. No source edits or broader tests were performed.

## Final verdict after takeover fix

**Approved within the narrow reviewed scope; no outstanding Critical or Important findings.** Reinspected `pet_s3_input_menu.inc:153`: realtime PTT edges clear only the presentation flag and return without starting/stopping audio or sending a PTT action. Reinspected `pet_s3_renderer_ui.inc:104`: `!realtime` prevents stale recording feedback from replacing captions during takeover. The accurate recording prompt, `对话回看` heading, and realtime footer (`切换回看  长按返回退出`) are present.

Both current production C harness tests in `s3_native_ui_test.py` passed in this final review by direct Python function invocation with their existing UBSan/compiler settings. The expanded input test covers normal PTT start/stop, realtime ownership, and normal-PTT-to-realtime takeover; the UI test rejects stale recording feedback and Agent cards in realtime mode. This verdict supersedes the earlier “with fixes” assessments. No further review expansion, source edits, broad test runs or hardware access were performed.
