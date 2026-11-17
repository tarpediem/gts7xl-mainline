# Upstream workflow for the gts7xl kernel patches (draft)

Status: preparation only. Nothing has been sent, no patch is committed anywhere, and no
`Signed-off-by` has been added for the owner. Every generated patch carries the placeholder
`Signed-off-by: <OWNER NAME> <OWNER EMAIL>` and the author `OWNER NAME <owner@example.invalid>`,
to be replaced by the owner before anything leaves the machine.

## 1. Identity, DCO and AI attribution

- `Documentation/process/submitting-patches.rst` asks for a sign-off "using a known identity
  (sorry, no anonymous contributions.)". The owner decides which name and address to use;
  that identity must be the author (`From:`) and the `Signed-off-by:` of every patch.
- `Documentation/process/coding-assistants.rst` (in our v7.3.4 tree): AI tools must not add
  `Signed-off-by`; the human submitter reviews the code, adds their own sign-off and takes
  responsibility. Contributions made with AI help carry an `Assisted-by:` tag. The drafts use
  `Assisted-by: Claude:claude-opus-5-5`; check the exact format required by the current
  version of that document before sending.
- The commits in `gts7xl-linux` carry `Co-Authored-By: Claude ...`. checkpatch flags it
  (BAD_SIGN_OFF, non-standard signature); the regenerated series below already replace it with
  `Assisted-by:`.
- Two files name the owner by his GitHub handle and address: the `maintainers:` field of
  `samsung,s6tuum3-amsa24vu01.yaml` and `st,fts1ba90a.yaml`, and `MODULE_AUTHOR()` in
  `panel-samsung-s6tuum3.c`. Replace them with the identity chosen above (the binding
  maintainer must be a person who will answer mail).

## 2. Base

The `gts7xl` branch sits on the **stable** tag `v7.3.4`. Upstream submissions must be based on
the target subsystem's `-next` branch (or `linux-next`). linux-next was not fetched tonight, so
none of the series below has been rebased or checked against it: some files may have moved on
(max77705 charger, gpi, sm8250 ASoC, the qcom DTS Makefile). Rebase each series, rebuild, and
re-run every check below before sending.

## 3. How the drafts were produced

From a separate worktree (the branch itself is never touched):

```sh
git -C linux worktree add ../linux-upstream gts7xl --detach
cd linux-upstream
# one detached series per subsystem, from v7.3.4:
#  - fix-up commits are folded into the commit they fix
#    (panel: 929788b3b + f1ca9badd; touch: 3be9c1361 + 435b40e87;
#     charger: 0d11871b2 + f38b6835f; board DTS: all 18 DTS commits);
#  - bindings are split from drivers (DT_SPLIT_BINDING_PATCH);
#  - messages reworded (capitalised subjects, Assisted-by, SoB placeholder).
git format-patch --cover-letter --base=v7.3.4 -o <scratch>/series/<n>-<name> -<k> HEAD
```

The generated series live in the session scratch directory only; they contain the placeholder
identity and are not committed. Regenerate them after the rebase with the same split (the
per-series files in this directory list the exact commits and paths).

Checks run on each series:

| Check | Command | Result |
|---|---|---|
| Style | `scripts/checkpatch.pl --strict` | per series file; the only errors left everywhere are the placeholder sign-off (`NO_AUTHOR_SIGN_OFF`, `BAD_SIGN_OFF`) |
| Bindings | `make dt_binding_check DT_SCHEMA_FILES=...` (dtschema 2026.9, in a scratch venv) on the 6 touched schemas | clean |
| Board DTB | `make CHECK_DTBS=y qcom/sm8250-samsung-gts7xl.dtb` | 1 warning (simple-framebuffer `required-opps`) |
| dtc W=1 | `make W=1 qcom/sm8250-samsung-gts7xl.dtb` | nothing from the board file (one existing warning in `sm8250.dtsi`, dsi1) |
| Maintainers | `scripts/get_maintainer.pl --no-git --no-git-fallback` | per series file |
| W=1 build of the touched objects | not run: the host lacks `bc` and `ld.lld`; the kernel is only built inside pmbootstrap, without W=1. Run `make W=1 C=1` (sparse) on each series after the rebase |

## 4. b4 workflow (suggested)

`b4` is not installed here; `uv tool install b4` (or the distribution package) gives it.

```sh
# one b4 branch per series, created from the subsystem's -next
b4 prep -n gts7xl-s6tuum3 -f drm-misc/drm-misc-next
git cherry-pick <the series commits>          # or git am the scratch patches
b4 prep --edit-cover                          # paste the cover letter draft
b4 prep --auto-to-cc                          # runs get_maintainer.pl
b4 prep --check                               # checkpatch + dt checks hooks
b4 send --reflect                             # sends to yourself only: read it in a mail client
b4 send                                       # the real thing (needs the owner's go)
# after review: amend, b4 prep --edit-cover (changelog), b4 send (v2 is automatic)
b4 trailers -u                                # collect Reviewed-by / Acked-by from the list
```

`b4 send` uses the kernel.org web endpoint or the owner's SMTP. Patch attestation
(`b4 send` signs with the owner's key when configured) is optional but welcome.

Rules to keep in mind for every series:

- one logical change per patch, imperative subject with the subsystem prefix used in
  `git log --oneline -- <file>` of that file;
- bindings first in a series, then the driver, then (in a separate series to the qcom tree)
  the DTS that uses them;
- `Fixes:` + `Cc: stable@vger.kernel.org` only on real bug fixes, sent before the features;
- wait at least a week between versions, answer every review comment, carry tags forward;
- no `RFC` on series that are meant to be merged, `RFC` on the ones that need a design
  answer first (marked below).
