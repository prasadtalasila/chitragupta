# Edge and cloud placement for digital twins

<!-- BENCH FIXTURE. Four gradings of one real claim from a real corpus
     paper, for bench/bench_overlap_embed.py's capability arm.

     The claim is the opening sentence of `singh_offload_2022`
     (Singh, Kovacs and Kiss, "Modelling the Offload Decision...", p.1):

       "The relatively close proximity of Edge Computing nodes to users
       in comparison with the distance to consolidated data centres in
       Cloud Computing has generated considerable recent interest in
       understanding how Internet of Things (IoT) devices could benefit
       from accessing edge servers rather than relying solely on cloud
       resources to process data."

     Each section below restates it at a different distance from the
     original, and each *cites* it -- which is the shape the failure mode
     actually takes in this pipeline's drafts. #134's hand read of the
     real book found 59 close-paraphrase candidates and they were
     overwhelmingly cited-not-quoted restatements of a source's own
     specific claim, not lifts from uncited papers. It is also the only
     shape tier 3 can see at all: the tier compares a section against
     the citekeys its dossier records, so a lift from a source the
     section never cited is outside its scope by construction (tiers 1
     and 2 scan the whole corpus and are what catch that).

     The four grades, in order, are the ones #134's 2026-08-14 comment
     established as the ladder tier 2 falls off partway down:
     verbatim -> in-place substitution -> light edit that moves words ->
     genuine restatement. -->

## Where the computation goes

A digital twin has to run somewhere, and "somewhere" is a decision with
consequences that outlast the deployment. Placing the twin's model close
to the asset shortens the loop between a measurement and a response;
placing it in a data centre buys computation the asset's own site cannot
justify owning. Most real systems end up doing both, which turns
placement from a one-off choice into a scheduling problem.

## Verbatim: the offload argument as its source states it

The relatively close proximity of Edge Computing nodes to users in
comparison with the distance to consolidated data centres in Cloud
Computing has generated considerable recent interest in understanding how
Internet of Things (IoT) devices could benefit from accessing edge servers
rather than relying solely on cloud resources to process data
[@singh_offload_2022]. That interest is what makes the placement question
worth a chapter rather than a footnote.

## Word substitution: the same sentence, words swapped in place

The comparatively short distance of Edge Computing nodes to users
compared with the separation from consolidated data centres in Cloud
Computing has produced substantial recent attention in appreciating how
Internet of Things (IoT) devices might gain from reaching edge servers
instead of depending only on cloud resources to handle data
[@singh_offload_2022]. The wording differs; the sentence does not.

## Light paraphrase: the same order, a few words moved and added

Because Edge Computing nodes sit comparatively close to their users --
much closer, at any rate, than the consolidated data centres that Cloud
Computing consolidates work into -- there has been a good deal of recent
interest in working out just how much Internet of Things devices stand to
gain by reaching an edge server directly, rather than depending on cloud
resources alone whenever they have data to process [@singh_offload_2022].
The argument survives the rewrite intact.

## Genuine restatement: the same claim, rebuilt

Proximity is the whole of the argument. An edge node is near the devices
it serves in a way a consolidated data centre never is, and that single
fact is why so much recent work asks whether an IoT device is better off
sending its data a short distance to a nearby server than a long one to
the cloud [@singh_offload_2022]. Nothing of the original phrasing
survives here; the claim is unchanged.

## What placement costs to get wrong

Whichever way the decision goes, it is expensive to revisit. A twin built
against the latency budget of a co-located edge node does not simply move
to a data centre when the fleet grows, and a twin built for cloud-scale
computation cannot be pushed to a device that has neither the memory nor
the power budget for it.
