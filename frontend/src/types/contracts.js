/** @typedef {{id:number,code:string,day:string,venue:string,play:string,channel:string,gross_cents:number,refund_cents:number,fee_cents:number,seats:number,checked:number,manual_checked:number|null,verification_id:number|null}} Settlement */
/** @typedef {{id:number,name:string,row_dim:string,col_dim:string,state:string,result:object}} Pivot */
/** @typedef {{id:number,pivot_id:number,row_key:string,col_key:string,book_cents:number,expected_cents:number,difference_cents:number,status:string,note:string}} Review */
/** @typedef {{id:number,device:string,event_no:string,ticket:string,session:string,happened_at:string,action:string,received_at:string}} GateEvent */
/** @typedef {{id:number,session:string,state:string,input_version:number,computed_version:number,retry_count:number,result:object,error:string}} Verification */
/** @typedef {{id:number,verification_id:number,ticket:string,entered_at:string,exited_at:string|null}} PresenceInterval */
/** @typedef {{id:number,verification_id:number,kind:string,ticket:string,happened_at:string,reason:string,device:string,event_no:string}} GateAnomaly */
