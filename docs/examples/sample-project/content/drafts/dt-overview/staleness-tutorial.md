# Detect a Stale Digital Twin in Twenty Minutes

You will build a staleness monitor for a simulated digital twin: a
script that watches a twin's state file and says, on every read,
whether the value can be trusted. By the end you will see the monitor
catch a simulated link failure that a naive reader would have missed.

You need Python 3.10 or newer and a terminal. Nothing else.

## 1. Simulate a twin's state file

A twin's live state, reduced to the smallest thing that can go stale: a
file holding one value and the time it was written. Create `twin.py`:

```python
import json, random, time

while True:
    state = {"temperature": 20 + random.random(), "written": time.time()}
    with open("state.json", "w") as f:
        json.dump(state, f)
    time.sleep(1)
```

Run it in one terminal and leave it running:

```console
$ python twin.py
```

## 2. Read the state naively

In a second terminal, create `read_naive.py`:

```python
import json

with open("state.json") as f:
    state = json.load(f)
print(f"temperature: {state['temperature']:.2f}")
```

```console
$ python read_naive.py
temperature: 20.73
```

It prints a temperature every time -- including, as you are about to
see, when the value is minutes old.

## 3. Mark staleness instead

Create `read_marked.py`. The only change is that the reader compares
the write timestamp with its own clock and refuses to present a stale
value as current:

```python
import json, time

STALE_AFTER = 3.0  # seconds

with open("state.json") as f:
    state = json.load(f)
age = time.time() - state["written"]
if age > STALE_AFTER:
    print(f"STALE ({age:.0f}s old) -- last known temperature: {state['temperature']:.2f}")
else:
    print(f"temperature: {state['temperature']:.2f} ({age:.1f}s old)")
```

```console
$ python read_marked.py
temperature: 20.31 (0.4s old)
```

## 4. Break the link, and watch the difference

Stop `twin.py` with `Ctrl-C` -- this is your link failure. Wait ten
seconds, then run both readers:

```console
$ python read_naive.py
temperature: 20.31

$ python read_marked.py
STALE (11s old) -- last known temperature: 20.31
```

The naive reader is confidently wrong: it presents an eleven-second-old
value with no hint that the twin has stopped tracking reality. The
marked reader gives you the same information and the honesty to use it.

Restart `twin.py` and run `read_marked.py` again to see it recover on
its own -- staleness is a property of the read, so no reset is needed.

## 5. Where you are

You have a twin, a link failure, and a reader that cannot be fooled by
one. The pattern -- carry the write time with the state, and make every
read compare it against a staleness budget -- scales unchanged from
this one file to a production state stream.

## Where to go next

Explicit staleness marking roughly halved operator mistrust incidents
in a comparative study of synchronisation strategies
[@sample_dt_sync_2023], and the factory case study shows what silent
staleness costs when it is not marked: both of its recorded failures
were divergences nobody was told about [@sample_dt_factory_2022]. For
the vocabulary of what you just built -- and why it is a shadow, not
yet a twin -- see [@sample_dt_overview_2024].

## References

[1] C. Chen and D. Devi, "State Synchronisation Strategies for Operational Digital Twins," *Synthetic Sample Papers*, vol. 1, pp. 6–11, 2023. `sample_dt_sync_2023`

[2] E. Eriksen, "A Digital Twin on the Factory Floor: an Eighteen-Month Case Study," *Synthetic Sample Papers*, vol. 1, pp. 12–17, 2022. `sample_dt_factory_2022`

[3] A. Author and B. Builder, "Digital Twins: Definitions, Distinctions, and a Short Taxonomy," *Synthetic Sample Papers*, vol. 1, pp. 1–5, 2024. `sample_dt_overview_2024`
