# The Error Table That Wouldn't Write

*A debugging story about why "the code comment said so" is not evidence.*

## The symptom

Our Silver layer runs every row through Spark-Expectations before it lands.
Rows that pass move on; rows that fail are supposed to be written to an *error
table* — a durable audit trail of exactly what got rejected and why. On a
medallion pipeline serving a Patient 360 product, that audit trail is not a
nicety. It is the difference between "we dropped 412 allergy records last
Tuesday and here they are" and a shrug.

The error table never wrote. And it didn't fail politely. It threw this:

```
java.lang.ArrayIndexOutOfBoundsException: Index 0 out of bounds for length 0
    at io.unitycatalog.spark.UCSingleCatalog$.fullTableNameForApi(UCSingleCatalog.scala:346)
    at io.unitycatalog.spark.UCProxy.loadTable(UCProxy.scala:386)
```

An `ArrayIndexOutOfBoundsException` from inside the catalog connector. Not a
`TableNotFound`, not an `Unsupported`, not a permission error — a raw
off-by-array-bounds crash from library code we don't own. The kind of stack
trace that tells you *something* is malformed but refuses to say what.

## The plausible answer that was already written down

When the AI agent first opened the code, it found the explanation waiting for
it. Sitting right above the disabled error-table writer was a comment, left by
an earlier pass, that read — in effect — *"error table disabled: RTAS/CTAS not
supported by Unity Catalog per Decision 12."*

This was a *perfectly plausible* story. We already knew Unity Catalog OSS 0.4.0
rejected `saveAsTable` — that limitation was the reason our entire write path
used pre-created external tables and `insertInto` instead. Spark-Expectations
writes its error table with `saveAsTable`. So of course it failed. Case closed.
The comment agreed, the architecture agreed, the symptom was consistent. An
agent optimizing for a fast, confident answer would have written "known UC
limitation, working as designed" and moved on.

It was also wrong.

## The tell

The thing that should stop you — and the thing we trained the agent to treat as
a stop sign — is the *shape* of the error. "RTAS not supported" is a decision a
catalog makes deliberately. When a system refuses to do something on purpose, it
tells you so on purpose: it throws `UnsupportedOperationException: REPLACE TABLE
AS SELECT (RTAS) is not supported`. It does not throw
`ArrayIndexOutOfBoundsException: Index 0 out of bounds for length 0`.

A clean, named refusal and a raw array crash are not the same failure wearing
two outfits. They are two different failures. The comment explained the wrong
one.

So instead of trusting the comment, we ran the experiment.

## Capturing the real exception

We isolated `saveAsTable` against UC 0.4.0 in controlled probes — not the
full pipeline, just the single operation under suspicion, varied one knob at a
time. What it actually threw, every time, was clean and named:

- On overwrite: `UnsupportedOperationException: REPLACE TABLE AS SELECT (RTAS)
  is not supported`, raised from `UCSingleCatalog.stageCreateOrReplace`.
- On create-new: `ApiException: 400 FAILED_PRECONDITION ... Neither catalog nor
  schema has managed location configured`, from `createStagingTable`.

Both were honest. Neither was an `ArrayIndexOutOfBoundsException`. The "RTAS"
comment described a *real* UC limitation — just not the one crashing our error
table. The connector was perfectly capable of telling us it didn't support
something. Our crash came from somewhere it *wasn't even getting that far*.

## The real root cause

So we reproduced the actual crash — re-enabled the error table in an isolated
run and read the trace it left, line by line, into the connector's source.

Spark-Expectations builds the error-table name by convention: it takes the
target table and appends `_error`, producing `synthea_allergies_error`. A
**bare** name. No catalog, no schema — just the table. It then asks the catalog
to load it.

Unity Catalog's connector takes that bare name and tries to qualify it into a
fully-qualified `catalog.schema.table` for its REST API. To find the schema, it
reads the session's *current database*. In our Spark-submit job, nothing had set
a current database, so it was empty. The connector split the empty namespace
into an array, got an array of length zero, and reached for `namespace[0]`.

```
fullTableNameForApi(name)  →  namespace = []  →  namespace[0]  →  💥 index 0, length 0
```

That was the whole bug. Not RTAS. Not CTAS. Not Decision 12. A bare table name
plus an empty current-database, meeting a connector that assumed the namespace
would never be empty. The `ArrayIndexOutOfBoundsException` wasn't UC refusing an
operation — it was UC *crashing while trying to figure out what we'd even asked
for*.

We proved it the only way that counts: we set the current database to `bronze`
and ran it again. The `ArrayIndexOutOfBoundsException` vanished — replaced by a
clean `SCHEMA_NOT_FOUND`. Same operation, one variable changed, and the crash
turned into a sentence. That's the signature of a confirmed root cause: you can
turn the symptom on and off at will.

## Why this is the chapter, not a footnote

Notice what almost happened. The agent had a complete, internally consistent,
documented explanation handed to it on a plate — and that explanation was false.
Every signal pointed the same wrong way: the comment, the architecture, the
prior decision, even the broad fact that UC 0.4.0 *does* reject `saveAsTable`.
Confirmation was everywhere. The truth was only reachable by ignoring all of it
and asking the system directly.

This is the part of working with AI agents that people underweight. The risk is
not that the agent can't find an answer. The risk is that it finds a *good* one
too easily — fluent, sourced, consistent with the surrounding code — and ships
it. A misdiagnosis that contradicts the evidence gets caught. A misdiagnosis
that *agrees* with a stale comment sails straight through code review, because
the reviewer reads the comment too.

The guardrail isn't a smarter model. It's a working principle, enforced on the
agent the same way you'd enforce it on a junior engineer:

> **A stack trace is evidence. A code comment is a hypothesis.**
> When they disagree, the trace wins — and you don't get to claim a root cause
> until you can turn the symptom on and off by changing one variable.

The agent that earns its keep is not the one that answers fastest. It's the one
that treats a plausible, pre-written explanation as the *beginning* of an
investigation instead of the end — that reads the actual exception, runs the
one-variable probe, follows the trace into the library's own source, and
reproduces the failure before naming its cause. We didn't get a correct answer
because the model was clever. We got it because the process refused to accept a
convenient one.

## The epilogue: knowing the fix, choosing the workaround

Once the cause was real, the fix options were obvious and we tested them too.
Newer Unity Catalog (0.5.0, built from source) fixed the connector's
empty-namespace handling outright — the error table wrote cleanly, ten rejected
rows and all. But the honest engineering call wasn't "upgrade four coupled
components to chase a preview-grade feature." It was: qualify the name and give
the writer a schema — and where we couldn't reach into the third-party writer,
fall back to a path-based write that needs no catalog round-trip at all. Same
audit trail, none of the version risk.

Which is the second lesson, quieter than the first: *finding* the true root
cause and *adopting the maximal fix for it* are different decisions. The
investigation tells you what's true. It doesn't get to tell you what to ship.
