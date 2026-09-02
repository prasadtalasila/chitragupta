# Synchronisation and Staleness

A digital twin's promise is currency, and currency decays between
synchronisations. This chapter covers how state moves and how a read
stays honest about its age.

## Synchronisation strategies

Comparing periodic pull, threshold push and event-driven flows,
event-driven synchronisation cut transmitted volume by 71 percent
against one-second polling while holding worst-case staleness under two
seconds -- and threshold push, the seemingly sensible middle ground,
produced the study's worst staleness excursions during slow drift its
delta never noticed [@sample_dt_sync_2023].

## Marked reads

Strategy alone is not honesty. A twin must know its own age: every read
should carry the value's staleness, so a broken link degrades visibly
instead of serving old values as current. Explicit staleness marking
roughly halved operator mistrust incidents in the same trials
[@sample_dt_sync_2023], and eighteen months of factory operation show
why the alternative is costly -- both failures in that record were
silent divergences between plant and model, and the study's
recommendation is to treat any such divergence as a severity-one defect
[@sample_dt_factory_2022].

The chapter's rule of thumb: derive the staleness budget from each
decision's physics, mark every read against it, and publish the record.
