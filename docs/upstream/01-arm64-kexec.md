# Series 1 — arm64: kexec: Mark machine_kexec() __nocfi

Readiness: **ready after two checks** (Fixes tag, not already fixed upstream).

## Patches

| # | Subject | Source commit | Files |
|---|---|---|---|
| 1 | `arm64: kexec: Mark machine_kexec() __nocfi` | 50fbe0d8a | `arch/arm64/kernel/machine_kexec.c` |

Single patch, no cover letter needed (`git send-email` / `b4 send` without one is fine for one
patch).

## Checks

- checkpatch --strict: `MISSING_FIXES_TAG` (the `Fixes:` line is a placeholder) + placeholder
  sign-off. Nothing else.
- Hardware: kexec -e worked from kernel r12 on, with CONFIG_CFI=y, many times since (it is the
  daily dev loop).

## Recipients (get_maintainer.pl)

- To: Catalin Marinas <catalin.marinas@arm.com>, Will Deacon <will@kernel.org>
- Cc: Mark Rutland <mark.rutland@arm.com>, linux-arm-kernel@lists.infradead.org,
  linux-kernel@vger.kernel.org, stable@vger.kernel.org (via the tag)
- Also worth Cc'ing for kCFI: Sami Tolvanen and Kees Cook (not listed by the script; check
  `MAINTAINERS` "CONTROL FLOW INTEGRITY").
- Tree: arm64 (`for-next/fixes`).

## Commit message (draft)

```
arm64: kexec: Mark machine_kexec() __nocfi

With CONFIG_CFI, kexec -e oopses in machine_kexec(): the indirect call
to kern_reloc first loads the type hash at target - 4 through the idmap
installed in TTBR0, and that address is in the page before the
relocation page, which is not mapped (level 3 translation fault at
kern_reloc - 4, pc machine_kexec+0x12c = ldur w16, [x8, #-4]). The
relocation code is copied from a SYM_CODE block and has no hash anyway.
Mark machine_kexec() __nocfi, as swsusp_arch_resume() already is.

Fixes: <TBD>
Cc: stable@vger.kernel.org
Assisted-by: Claude:claude-opus-5-5
Signed-off-by: <OWNER NAME> <OWNER EMAIL>
```

## Must do before sending

1. **Search lore and linux-next** for an existing fix (`machine_kexec` + `cfi` / `nocfi`):
   arm64 + kCFI is common, it may already be fixed or reported. If a fix exists, drop this.
2. **Fixes tag**: our tree is a shallow stable checkout. In a full clone, find the commit that
   made the jump to `kern_reloc` a kCFI-checked indirect call (`git log -S kern_reloc --
   arch/arm64/kernel/machine_kexec.c`, and when arm64 kCFI landed), and fill it in.
3. Add the oops trace (a few lines of the actual splat from the r10/r11 logs) to the message;
   arm64 maintainers like to see it.
4. Mention the test platform in the message or below the `---`.
