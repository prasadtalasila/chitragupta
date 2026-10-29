# figure-drawer: the taste gate

Read this once you know the figure's pattern and layout, and before
anything is written. The caller has decided that a figure is warranted.
This gate decides how little of one will do, and it can conclude that
the answer is none, or two. It costs a minute; a figure drawn, checked
and looked at, then dropped, costs much more.

Answer the five questions in order. §2 to §4 trim the figure, and you
apply them yourself. §1 and §5 can end in a *structural* verdict, which
goes back to the caller (§6).

## 1. A sentence or a table

Say what the figure argues in one sentence. If that sentence, written in
the prose, would tell the reader everything the figure does, the figure
is decoration: a two-box "A sends to B" is a sentence. If the content is
attributes compared across items, rather than relations between them,
it is a table: a figure whose nodes all carry the same three fields and
whose edges carry nothing is a table drawn badly. Either answer is
structural.

## 2. The remove test

For each node, edge and label, ask what the reader loses if it goes. If
the answer is nothing the argument needs, cut it. Typical cuts:

- a node the prose never mentions and no edge depends on;
- an edge that restates an order the layout already shows, such as one
  layer of a stack to the next. A pipeline's or a loop's edges are its
  argument: keep them;
- a gloss that repeats its node's name;
- a legend entry for a style used once, where a tag would do.

Compare the result with the layout's reference ranges in its file under
`layouts/`. A figure far above them usually still has something to cut;
far below, check §1 again. The ranges are references, never caps.

## 3. Nodes that travel together

Two nodes that always appear together, with an edge between them and no
other edge into or out of the pair, are one node to this argument. Merge
them, and name the merged node for what the pair does. Keep them apart
only when the edge between them is the point.

## 4. One focal node

Name the one thing the figure is about, and mark it `cgkey`. A map or a
layered stack may argue about positions or levels, with no single node
as the point; then mark none. A pipeline, loop, spine, hub or tree with
no nameable focus has no claim yet: go back to the pattern. If you name
two, either one of them is not the point, or this is two figures (§5).
`figure check` reports more than one `cgkey` node as `focal-count`, but
by then the figure is drawn.

## 5. One figure or two

It is two figures when:

- it argues two things, and §4 found two focal nodes;
- one part is an overview and another zooms into one of its nodes, which
  is overview and detail, one figure each;
- it would need two layouts, a pipeline with a hub inside one stage, for
  instance.

Panels are not the answer to two arguments. Panels compare like with
like, in one argument (`figures.md` §2).

## 6. What goes back to the caller

A trim (§2 to §4) is yours: make it, and list what was cut in the
return.

A structural verdict ("a sentence does this", "a table does this", "this
is two figures: an overview of X and a detail of Y") is the caller's to
decide, because it changes the draft and not only the figure. Draw
nothing. Return the verdict, its one-sentence reason and, for a sentence,
the sentence. The caller may agree, or may ask for the figure anyway. On
direct use the caller is the person who asked: put the verdict to them,
and draw only if they still want the figure.
