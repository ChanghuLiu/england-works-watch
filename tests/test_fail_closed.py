from england_works_watch.policy import assess_change_impact
def test_unknown_event_fails_closed(): assert assess_change_impact({'route':'skilled_worker','event_type':'mystery'})['status']=='INSUFFICIENT_INPUT'
def test_salary_decrease_never_guesses_thresholds():
    r=assess_change_impact({'route':'skilled_worker','event_type':'salary_change','direction':'decrease'}); assert r['status']=='INSUFFICIENT_INPUT'; assert 'same_salary_option_still_met' in r['missing_inputs']
def test_location_conflict_review_required(): assert assess_change_impact({'route':'skilled_worker','event_type':'work_location_change','hybrid_only':True,'permanent_remote':True})['status']=='REVIEW_REQUIRED'
