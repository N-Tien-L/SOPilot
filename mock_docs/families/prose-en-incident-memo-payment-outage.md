To all engineering and customer support staff,

This memo summarises the payment outage that affected customers on the evening of 9 March, explains what we found, and describes what we are changing so that it does not happen again. It is written for people who were not on the call, so some background is included.

At 18:42 UTC our monitoring began to show a rising rate of failed card payments. Within ten minutes roughly one in three attempts was failing with a timeout. The on-call engineer was paged at 18:47, confirmed the problem and opened an incident at 18:55. Customer support started receiving tickets at about the same time, and by 19:30 more than four hundred had been logged.

The first hour was spent looking in the wrong place. Because the errors were timeouts, the team suspected the payment provider and spent time on a call with their support team, who reported no issues on their side. In reality the problem was inside our own network. A routine certificate rotation earlier that afternoon had replaced the certificate on the payment service but not on the internal gateway that sits in front of it. The gateway accepted the old certificate for existing connections, which is why the system looked healthy at first, and then started rejecting new connections as the old ones were recycled during the evening peak.

The cause was identified at 19:58 by an engineer who compared the certificate fingerprints on the two hosts and noticed they did not match. The gateway certificate was replaced and the service restarted at 20:12. Payment success returned to normal levels at 20:20, and we kept the incident open for another hour to watch for regressions. In total, customers could not reliably pay for about ninety minutes, and we estimate that around eleven thousand attempted orders were affected, of which about sixty percent were completed later when customers retried.

Several things went wrong that we want to fix. The certificate rotation was done by hand and the checklist did not include the gateway, because the gateway was added to the architecture after the checklist was written. Our alerts fired on the failure rate but did not point to certificates, so the first responders had no hint about the real cause. And the incident channel was used for both investigation and customer updates, which made it hard to follow the technical thread and delayed the first public status message until 19:40.

We have agreed the following actions. The certificate rotation will be automated so that every service and gateway is updated from a single source, and the manual checklist will be retired by the end of April. A new alert will warn seven days before any certificate expires and when two hosts in the same path present different certificates. Incident communication will be split into a technical channel and a separate channel for support and status updates, with a named communications lead assigned at the start of every incident. We will also run a short exercise next month where the team practises a gateway failure without advance notice.

Finally, we would like to thank the support team for handling a large number of upset customers with patience, and the engineers who stayed late to find the cause. A full timeline and the list of follow-up tasks with owners will be shared in the engineering wiki by Friday. If you spotted something we missed, please reply to this memo or bring it to the review meeting on Thursday.

Regards,
The platform team
