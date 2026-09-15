<!-- Outline. Edited by hand before drafting. Per `##`-or-deeper heading:
     `brief:` (steering, never appears in the draft) and/or one or more
     `claim:` blocks (your own prose, rewritten -- every sentence that
     can't be grounded is reported rather than shipped), and an
     optional `queries:` list of the search terms to run verbatim
     instead of the skill inventing sub-themes.

     A tutorial's outline is mostly briefs: the steps come from walking
     the path, not from the corpus. `queries:` appears once, in the
     closing section -- the only place this genre may cite.
-->

# Lab 2 -- Build a digital twin of a water tank

## What you will build

brief: Show the destination first, as the literal terminal output the
learner will see at the end -- three lines of it, verbatim. Seeing the
end result is what makes someone willing to start.

## What you will learn

brief: Phrased as capability, not curriculum. "You will be able to..."
Three items, no more.

## What you need

brief: Exact versions, never "a recent Python". Python 3.11+, the
`tanksim` package from the course repository, a terminal. Say the lesson
takes 45 minutes and mean it.

## Step 1 -- Get the simulator running

brief: One action, and it ends with the command that proves it worked
plus the output that command prints. Every step in this lesson ends that
way; a step whose success the learner cannot see is where a lab goes
quiet.

## Step 2 -- Read one measurement

brief: Deliberately trivial. Its job is to establish the loop and the
print, so step 3 can be about the estimator and nothing else.

## Step 3 -- Add the estimate

brief: The two lines of arithmetic from chapter 3, with the gain given
as a constant. Do not derive it here -- the derivation is the chapter,
and repeating it stops the lesson dead.

## Step 4 -- Watch it correct itself

brief: The payoff step. The learner changes the inflow by hand and
watches the estimate track it. If a learner cannot see this happen, the
lesson has failed, so the step ends with what the numbers should look
like before and after.

## What you built

brief: Restate what now works, in the learner's terms. Two sentences.

## Where to go next

brief: The only section that may cite. Point at the two corpus papers
that frame what was just done by hand, plus chapter 4 for the matrix
form and the tuning question deferred from step 3.

queries:

- state estimation introduction survey
- digital twin synchronisation
