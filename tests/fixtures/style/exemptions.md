# Style fixture

This file proves that the vendored `assets/vale/` still parses and that
each quoted-span exemption still holds. Every defect marker and every
American spelling below sits inside an exemption, so a correct run reports
**nothing at all**. Anything reported here means an exemption has broken,
not that this prose is wrong.

```python
simply = "obviously inside a fenced block"
```

An inline `simply` code span, and a fenced one above.

> A quoted source that says obviously, and spells it color.

## 3.13 References

- P. Smith, "Simply a Study of Color Organization," 2020.
