/** Fixed N16R8 wiring: previous GPIO39, next GPIO38, confirm GPIO0. */
export function s3ButtonRows(actionOptions = ['session_previous','session_next','page_enter','page_back','component_center','voice_ptt','realtime_chat','agent_prompt','disabled']) {
 return ['上一个','下一个','确认'].flatMap((label,index) => ['short','long'].map(gesture => {
  const sw = index + 1;
  const long = gesture === 'long';
  return {id:`s3_sw${sw}_${gesture}`,controlId:`s3_sw${sw}`,label:`${label} ${long?'长按':'短按'}`,
   event:`button.sw${sw}.${long?'long_press':'short_press'}`,
   ...(long ? {holdEvent:`button.sw${sw}.hold`, voiceTriggerId:`sw${sw}.hold`,voiceFallbackAction:'disabled'} : {}),
   defaultAction:[['session_previous','page_back'],['session_next','component_center'],['page_enter','voice_ptt']][index][long?1:0],
   actionOptions:long?['voice_ptt',...actionOptions]:actionOptions.filter(a=>a!=='voice_ptt'), supportsValue:true};
 }));
}
