# Chapter 3: Staleness, and Why a Twin Must Know Its Own Age

## Learning objectives

After this chapter you can: (1) define staleness and compute it from a
timestamped reading; (2) choose a staleness budget from a decision's
tolerance rather than a technology's habit; (3) explain why a stale
value served as current is worse than no value at all.

## 3.1 Motivation

A digital twin promises a current picture of a physical asset, and
everything built on the twin -- dashboards, predictions, schedules --
inherits that promise. The promise breaks quietly: links drop,
publishers pause, clocks drift. Field studies report that the costly
failures are precisely the quiet ones, where the representation and the
asset part company without anyone being told
[@sample_dt_factory_2022], and that making the twin announce its own
uncertainty measurably improves how far operators trust it
[@sample_dt_sync_2023]. This chapter builds the smallest tool for that
honesty: knowing, at every read, how old a value is.

## 3.2 Definitions

Let a reading be a pair \(v, t_w\): a value and the time it was
written. A reader at time \(t_r\) observes **staleness**
\(s = t_r - t_w\). A **staleness budget** \(B\) is the largest \(s\) a
given decision tolerates; a reading with \(s > B\) is **stale for that
decision**. Staleness is a property of a read, not of a value: the same
reading can be fresh for a daily report and stale for a safety stop.

## 3.3 Worked example: one sensor, two decisions

A temperature reading is written at 09:00:00. A control loop with
\(B = 2\,\text{s}\) reads at 09:00:03: \(s = 3\,\text{s} > B\), stale
-- the loop must fall back to its safe action. A shift report with
\(B = 15\,\text{min}\) reads at 09:04:00: \(s = 4\,\text{min} < B\),
fresh -- the same value serves both readers differently, which is why
the budget belongs to the decision.

**Check yourself:** a reading written at 09:00:00 is read at 09:00:02
by the control loop and at 09:20:00 by the report. Which reads are
stale? (The first is fresh by one second; the second exceeds the
report's budget by five minutes.)

## 3.4 Worked example: choosing a budget

A packaging line stops safely within 4 s of a jam signal, and a jammed
line damages product after roughly 10 s. The decision "stop on jam" can
therefore tolerate at most \(10 - 4 = 6\,\text{s}\) between the jam
occurring and the decision seeing it. If sensing and transport already
consume up to 2 s, the staleness budget for the jam signal is
\(B = 4\,\text{s}\). The number came from the decision's physics, not
from how often the network happens to deliver.

## 3.5 What a stale read must do

Three behaviours, from worst to best. *Serve silently*: present the
last value as current -- the reader cannot distinguish an old 20 °C
from a fresh one, and this is the failure mode the field studies
record. *Refuse*: return an error -- honest, but discards the
information the last value still carries. *Serve marked*: return the
value with its age, letting each decision apply its own budget. Marked
service is strictly more informative than either alternative and costs
one timestamp per reading.

## Exercises

1. A reading carries \(t_w\) from a device whose clock runs 3 s ahead
   of the reader's. What does naive \(s = t_r - t_w\) report for a
   just-written value, and what could go wrong at a 2 s budget?
2. Extend the marked-read rule to a twin aggregating five sensors:
   propose and defend a definition of the aggregate's staleness.
3. Section 3.4's line is upgraded to stop within 2 s. Recompute the
   budget, and state the general formula.

## Summary

Staleness is the age of a value at the moment it is used; a budget
turns a decision's tolerance into a test; and a twin that serves marked
values converts silent failure into visible degradation -- the property
the operational literature identifies as what trust is actually built
on [@sample_dt_sync_2023; @sample_dt_factory_2022].

## References

[1] E. Eriksen, "A Digital Twin on the Factory Floor: an Eighteen-Month Case Study," *Synthetic Sample Papers*, vol. 1, pp. 12–17, 2022. `sample_dt_factory_2022`

[2] C. Chen and D. Devi, "State Synchronisation Strategies for Operational Digital Twins," *Synthetic Sample Papers*, vol. 1, pp. 6–11, 2023. `sample_dt_sync_2023`
