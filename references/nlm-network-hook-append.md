### Offline preparation registration / 離線封裝登記

`scripts/nlm_offline_preparation_guard.py` adds a separate, exact offline path for
reviewed static preparation, transport preparation and local maintenance
installation. It never executes the registered command. All other events are
passed unchanged to the pinned original network guard and its original policy or
network registry. It grants no route, query, controller or budget authority.

The installed hook uses a fixed command:

```text
<pinned-python> -BE <installed-dispatcher> --authority <installed-authority>
```

The authority file has schema `nlm-offline-preparation-authority-v1`, with complete
`dispatcher` and `registry` pins (`path`, `bytes`, `sha256`). It must be a canonical,
regular file owned by the current user, without group/other write permission.
Only the maintainer replaces it atomically, preserving the old file and evidence.
The hook command and client trust do not change when one offline item is added.
The dispatcher pins itself through that authority and uses a four-second local
deadline; neither this registration nor an explicit local allow proves that an
already-running client loaded its native hook.

The outer registry has exactly these fields:

```json
{
  "schema": "nlm-offline-preparation-dispatch-registry-v1",
  "network_guard": {"path": "<absolute>", "bytes": 0, "sha256": "<sha256>"},
  "network_authority": {
    "kind": "policy or registry",
    "file": {"path": "<absolute>", "bytes": 0, "sha256": "<sha256>"}
  },
  "offline_preparations": []
}
```

Each offline item uses `nlm-offline-preparation-v1` and contains `id`, `action`
(`static`, `prepare`, or `maintenance-install`), complete `argv`, complete
`python`, `script`, `input`, and `authorization` pins, a nonempty `dependencies`
pin list, `input_schema`, `authorization_schema`, `root_session`, and
`network: "none"`. Maintenance installation also fixes `plan_sha256`. Machine
paths, task schemas, identities and concrete commands belong only in the private
registry. `validate_offline_preparation(item, check_files=True)` is the shared
installation/dispatch validator. It checks exact argument order, all selected
files, input-to-authorization binding and the zero-network scope. The registered
program repeats its own actor, exact-input, output-exclusivity and plan checks.
Known route/query/admission call sites are refused; this narrow source check is
not a proof that arbitrary Python is harmless.

An inspect command does not authorize an added `--apply`. Changed code, inputs,
authorization, dependencies, flags, interpreter, shell composition, direct
transport or SDK execution cannot match an offline entry. Original SDK and
legacy network commands remain subject to their complete network policy and
runtime checks. Missing files for an unrelated, unselected offline item do not
invalidate an otherwise valid original network command.

The offline matcher covers an execution event with a literal `cmd` or `command`
field, including the standard `rtk proxy` prefix. It also accepts exactly one
complete `functions.exec` wrapper: `text(await tools.exec_command(<JSON>));`.
The JSON object has a required literal `cmd` and only optional literal `workdir`,
`max_output_tokens`, and `yield_time_ms`; duplicate keys are rejected. The event
may carry a source string or a sole `code` field. No JavaScript is evaluated.
The extracted command goes through the same exact offline checks. Added
statements, dynamic expressions, extra arguments or a second call do not gain
this exception and remain subject to the original network guard. Verify the
actual client event separately; an explicit local allow does not prove native
hook loading or execution.

Keep the dependency order acyclic: create the static input and exact offline
registration, generate the static contract, install the network policy for that
existing contract, then create and register the preparation input. The SDK's
internal network registry never points back to a preparation input. The mutable
outer registry and its fixed authority are separate. A maintenance input or plan
must not include the hash of an outer registry that contains its own input or
plan hash. The maintainer reads and preserves that current outer state at the
actual update, without weakening the separately pinned network policy.

離線登記只接受具名完整命令及固定檔案，不能以 `network: none` 標籤把原網路
腳本變成離線例外。先有 static 契約，再安裝對應 policy，最後產生 prepare
輸入；內部網路 registry 與可追加離線登記的外層 registry 分開，避免雜湊循環。
原網路 guard、帳號／來源、FIFO、額度與失敗紀錄仍依原契約處理。公開文件不
保存本機路徑、帳號、task ID 或任何實際登記內容。
