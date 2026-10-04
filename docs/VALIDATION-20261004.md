# Customer-flow validation — 4 October 2026

Purchase and recovery handlers now reject email addresses with a missing local part
or domain before contacting the commercial service. Existing field feedback and
submitted-answer preservation apply.

Local regression checks exercise both handlers’ rejection predicates. The full
product suite is run with its existing test runtime. Staging deployment status
and browser acceptance are recorded in the portfolio progress record; local tests
do not establish live Stripe, live mail delivery or visual browser acceptance.

Production is unchanged.
