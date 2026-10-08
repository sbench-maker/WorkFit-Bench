# Harborline pilot interview transcript

Recording note: fictional remote interview, May 21, 2026. Automated transcription was reviewed for speaker names only. Bracketed editorial notes are part of the source record.

001 [00:00] Jonah Kim: Thanks for making the time. I want to understand the work before we talk about the product.
002 [00:12] Mara Velez: Good. The work is less glamorous than the route map.
003 [00:18] Priya Shah: That is usually where the useful story is.
004 [00:25] Owen Reed: We have forty-five minutes. I will flag anything that still needs approval.
005 [00:34] Jonah Kim: Mara, what did a normal afternoon look like before the pilot?
006 [00:40] Mara Velez: Around three, each branch started protecting tomorrow while still trying to land today.
007 [00:49] Mara Velez: Coordinators had customer promises in branch spreadsheets.
008 [00:56] Mara Velez: Dispatch had routes in Northstar and exceptions coming through chat.
009 [01:04] Mara Velez: If a technician ran long, somebody had to line those three views up.
010 [01:12] Jonah Kim: Who was that somebody?
011 [01:16] Mara Velez: Whoever noticed first. That was part of the problem.
012 [01:22] Owen Reed: Sometimes a coordinator, sometimes the closing dispatcher.
013 [01:29] Mara Velez: And sometimes me, after I thought the day was done.
014 [01:37] Jonah Kim: Give me one concrete example.
015 [01:42] Mara Velez: A water-heater job runs ninety minutes over in the north branch.
016 [01:50] Mara Velez: The next customer has a four-to-six promise and cannot take a later arrival.
017 [01:58] Mara Velez: The route view shows an open slot elsewhere, but it does not show why that slot is open.
018 [02:06] Mara Velez: We move the job, then learn the second technician is carrying an eight-to-ten promise from the spreadsheet.
019 [02:15] Jonah Kim: So the repair is feasible, but the promise is not.
020 [02:19] Mara Velez: Exactly. Capacity is not the same as permission.
021 [02:27] Priya Shah: That sentence shaped the product review.
022 [02:34] Jonah Kim: What happened after the bad move?
023 [02:38] Mara Velez: Another dispatcher unwound it. Somebody called the customer. The route got solved twice.
024 [02:47] Mara Velez: Before this, we were solving the same route twice—once at 4 p.m. and again at 6.
025 [02:57] Jonah Kim: I may use that. We will confirm the wording.
026 [03:02] Owen Reed: Marking it for quote approval.
027 [03:09] Jonah Kim: Priya, what did Dispatch Windows add?
028 [03:14] Priya Shah: A coordinator can save the customer promise window on the work order.
029 [03:22] Priya Shah: Dispatch sees the window and the slack around it when considering a move.
030 [03:29] Priya Shah: The system recommends feasible moves that preserve the recorded promise.
031 [03:37] Priya Shah: A person still chooses whether to make the move.
032 [03:43] Jonah Kim: Does it reassign the technician automatically?
033 [03:48] Priya Shah: No.
034 [03:50] Jonah Kim: Does it contact the customer?
035 [03:54] Priya Shah: No. The dispatcher confirms the change, and the existing mobile view updates for the technician.
036 [04:03] Mara Velez: That boundary mattered to us. We did not want an optimization model making customer promises.
037 [04:12] Priya Shah: It can surface a conflict. It cannot make the service judgment.
038 [04:19] Jonah Kim: What did the first week expose?
039 [04:24] Mara Velez: Our spreadsheets were not as clean as we thought.
040 [04:29] Mara Velez: Some windows were arrival promises. Some were “customer prefers morning.”
041 [04:37] Owen Reed: We agreed to record only a promise the customer had actually received.
042 [04:44] Mara Velez: That made the field useful. It also forced a better conversation at booking.
043 [04:53] Jonah Kim: Was adoption immediate?
044 [04:57] Mara Velez: No. Two coordinators treated it as one more field for the first ten days.
045 [05:05] Mara Velez: They entered windows at the end of the shift, which misses the point.
046 [05:11] Owen Reed: The branch leads moved the check into the booking handoff.
047 [05:18] Mara Velez: By the last two weeks, eleven of fourteen coordinators used saved windows at least four days a week.
048 [05:28] Jonah Kim: That is a better adoption signal than login count.
049 [05:33] Priya Shah: Yes. Login count would tell us almost nothing here.
050 [05:39] Jonah Kim: Let us get the pilot size on tape.
051 [05:43] Owen Reed: Six weeks, April sixth through May seventeenth.
052 [05:50] Owen Reed: Fourteen coordinators across three Harborline branches.
053 [05:56] Mara Velez: And about two thousand jobs, right?
054 [06:00] Priya Shah: The reviewed count is one thousand eight hundred forty-two work orders.
055 [06:08] Owen Reed: Use 1,842. The earlier two-thousand figure was a rough estimate.
056 [06:17] Jonah Kim: What period did the team compare?
057 [06:21] Priya Shah: The six weeks immediately before the pilot against the six-week pilot.
058 [06:30] Jonah Kim: Not the same dates last year?
059 [06:33] Priya Shah: Correct. We did not have the same instrumentation last year.
060 [06:40] Jonah Kim: What moved first?
061 [06:43] Priya Shah: Median active scheduling time per work order.
062 [06:50] Priya Shah: It went from six minutes forty seconds to four minutes thirty-five seconds.
063 [06:59] Owen Reed: The approved change is thirty-one percent lower.
064 [07:05] Jonah Kim: I saw twenty-nine percent in an early deck.
065 [07:09] Priya Shah: That deck used the first five weeks. Thirty-one is the final reviewed result.
066 [07:18] Mara Velez: It felt like two hours back per coordinator every day.
067 [07:24] Owen Reed: We cannot publish that. We did not measure employee hours saved.
068 [07:32] Mara Velez: Fair. Call it my impression, not a result.
069 [07:38] Jonah Kim: I will leave the two-hour line out.
070 [07:44] Jonah Kim: What happened after hours?
071 [07:48] Priya Shah: The after-hours reassignment rate moved from 12.4% to 7.1%.
072 [07:58] Priya Shah: That is down 5.3 percentage points.
073 [08:04] Jonah Kim: Not 5.3 percent.
074 [08:07] Priya Shah: Correct. Percentage points.
075 [08:13] Mara Velez: That was the change my team noticed. Fewer routes came back after dinner.
076 [08:22] Jonah Kim: Did arrival performance move too?
077 [08:26] Priya Shah: On-time arrival increased from 82% to 88%.
078 [08:34] Owen Reed: Six percentage points.
079 [08:39] Mara Velez: We also got to zero missed appointments in the final week.
080 [08:46] Priya Shah: In the final week, yes, but that is not the approved pilot claim.
081 [08:54] Priya Shah: Across the full window, missed appointments moved from 5.8% to 4.9%.
082 [09:01] Owen Reed: Directional only. Six weeks is too short to separate that from seasonal demand.
083 [09:10] Jonah Kim: So it can appear with the limitation, but not as proof.
084 [09:14] Owen Reed: Exactly.
085 [09:20] Jonah Kim: Mara, what part of the product mattered in practice?
086 [09:25] Mara Velez: The useful part isn’t the map. It’s knowing which promise we can still keep.
087 [09:35] Jonah Kim: That is another possible quote.
088 [09:39] Owen Reed: Marked for approval.
089 [09:44] Mara Velez: The color coding is beautiful too, but do not write that. [laughs]
090 [09:50] Jonah Kim: Noted.
091 [09:55] Jonah Kim: What still requires judgment from dispatch?
092 [10:00] Mara Velez: Whether the customer relationship can absorb a change, even if the window technically allows it.
093 [10:08] Mara Velez: Whether a technician is the right person for that repair.
094 [10:14] Mara Velez: Whether moving one job creates a worse problem at the end of the route.
095 [10:22] Priya Shah: The recommendation does not erase those calls.
096 [10:28] Jonah Kim: Any workflow failure we should be honest about?
097 [10:33] Mara Velez: Saved windows go stale if the customer calls the branch and the note stays only in chat.
098 [10:42] Owen Reed: We added a branch rule: the person taking the call updates the work order before posting in chat.
099 [10:51] Mara Velez: That is not the software solving culture. It is the software giving the culture one place to land.
100 [11:00] Jonah Kim: What did the pilot not cover?
101 [11:04] Priya Shah: It was three branches at one residential maintenance operator.
102 [11:10] Priya Shah: There was no randomized control group.
103 [11:14] Owen Reed: We should not imply commercial service, emergency restoration, or every operating model.
104 [11:22] Mara Velez: Our branches also share some technicians. A fully independent branch model may behave differently.
105 [11:31] Jonah Kim: When does the feature launch?
106 [11:35] Priya Shah: General availability is June eighteenth.
107 [11:41] Owen Reed: The June twelfth date in the draft notes is superseded.
108 [11:47] Jonah Kim: Which plans?
109 [11:50] Priya Shah: Growth and Scale.
110 [11:55] Owen Reed: Not every paid plan. Packaging changed after the first draft.
111 [12:02] Jonah Kim: Is there a standalone price?
112 [12:05] Owen Reed: No approved price. Leave pricing out.
113 [12:10] Priya Shah: The forty-nine-dollar figure was a placeholder from a planning sheet.
114 [12:18] Jonah Kim: What are we trying to sustain after launch?
115 [12:23] Priya Shah: At least a twenty-five percent reduction in median active scheduling time.
116 [12:31] Priya Shah: And after-hours reassignment below eight percent.
117 [12:37] Jonah Kim: Those are launch targets, not more pilot outcomes.
118 [12:41] Priya Shah: Right.
119 [12:45] Mara Velez: Off the record, I would bet they beat both by August.
120 [12:51] Owen Reed: Off the record means it does not appear.
121 [12:56] Jonah Kim: Understood. What should a reader do after the issue?
122 [13:01] Owen Reed: Bring one week of after-hours reassignments to a Northstar workflow review.
123 [13:08] Mara Velez: Make them bring the actual late changes, not a clean summary.
124 [13:13] Priya Shah: That keeps the review tied to their operation.
125 [13:18] Jonah Kim: Last question. What would make this article feel false to you?
126 [13:24] Mara Velez: If it says the product found some magical route we could not see.
127 [13:31] Mara Velez: The gain came from getting the promise into the same place as the decision.
128 [13:38] Priya Shah: And if it turns targets into proof. We have one pilot, not a universal law.
129 [13:46] Owen Reed: Quotes will be final only if they appear in the approved facts file.
130 [13:52] Jonah Kim: Good. I have what I need. Thank you.
