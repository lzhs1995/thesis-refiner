"""明确的原控制器兼容入口；不迁移SDK runtime、预算、旧准备或旧请求。"""
import json
from pathlib import Path
import shlex
import sys
import time
import types


def source(entry, value, name):
    path = entry.checked(value); module = types.ModuleType(name)
    module.__file__ = str(path); module._dual_source_pin = value
    sys.modules[name] = module
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


def code_is_original(entry, function, reference, name):
    # 只比对原文件编译所得具名函数code，不执行额外runtime或重建预算。
    code = compile(entry.checked(reference).read_bytes(), reference['path'], 'exec')
    found = [v for v in code.co_consts if isinstance(v, types.CodeType) and v.co_name == name]
    entry.require(len(found) == 1 and function.__code__ == found[0], 'ORIGINAL_LEGACY_FUNCTION_REQUIRED:' + name)


def context(entry, path):
    cfg_ref = entry.ref(path); cfg = entry.read(cfg_ref)
    entry.require(cfg.get('schema') == 'nlm-legacy-task-v1', 'LEGACY_TASK_SCHEMA')
    entry.require(sys.flags.ignore_environment and sys.dont_write_bytecode and not sys.flags.optimize,
                  'PINNED_PYTHON_BE_REQUIRED')
    policy = entry.enforce_route_policy(cfg)
    entry.require(Path(sys.executable).resolve() == entry.checked(cfg['python']), 'PINNED_PYTHON_REQUIRED')
    entry.actor_check(cfg)
    entry.require(cfg.get('scripts') == str(entry.SCRIPTS)
                  and cfg.get('code_pins') == policy['code_pins'], 'LEGACY_ENTRY_CODE_CHANGED')
    entry.require(cfg.get('legacy_contract') in policy.get('legacy_contracts', []), 'REGISTERED_LEGACY_CONTRACT_REQUIRED')
    contract = entry.read(cfg['legacy_contract'])
    entry.require(contract.get('schema') == 'nlm-legacy-task-contract-v1'
                  and contract.get('status') == 'APPROVED_STATIC_LEGACY_CONTRACT', 'APPROVED_STATIC_CONTRACT_REQUIRED')
    for key in ('task_id', 'account_key', 'notebook_id', 'budget_root', 'resource_root', 'query_budget'):
        entry.require(cfg.get(key) == contract.get(key), 'LEGACY_STATIC_IDENTITY_CHANGED:' + key)
    entry.require(type(contract['query_budget']) is int and contract['query_budget'] > 0, 'ORIGINAL_QUERY_BUDGET_REQUIRED')
    entry.require(cfg.get('authorization') == contract['authorization'], 'ORIGINAL_AUTHORIZATION_CHANGED')
    for key in ('authorization', 'root_scope', 'runtime', 'broker_module', 'adapter', 'bridge',
                'original_request', 'prior_prepared_result'):
        entry.checked(contract[key])
    for value in contract['artifacts']: entry.checked(value)
    entry.require(all(contract[k] in contract['artifacts'] for k in ('runtime', 'broker_module', 'adapter', 'bridge')),
                  'COMPLETE_LEGACY_EXECUTABLE_PINS_REQUIRED')
    # CFG在binding之前固定；未来key/owner/决定只能位于后置RUN_SPEC。
    entry.require(not set(cfg) & {'legacy_prepared', 'legacy_binding', 'operation_adoption', 'request_key',
                                 'recovery_decision', 'run_spec'}, 'FUTURE_OUTPUT_IN_LEGACY_CONFIG')
    bridge = source(entry, contract['bridge'], 'approved_legacy_task_bridge')
    adapter = bridge.parent_adapter(cfg)
    entry.require(entry.ref(adapter.__file__) == contract['adapter'], 'EXACT_LEGACY_ADAPTER_REQUIRED')
    runtime = adapter.B.runtime()
    entry.require(entry.ref(runtime.__file__) == contract['runtime'], 'EXACT_ORIGINAL_RUNTIME_REQUIRED')
    code_is_original(entry, runtime.run_bound, contract['runtime'], 'run_bound')
    return cfg_ref, cfg, contract, bridge, adapter, runtime


def metadata(entry, ctx, operation_ref, *, request=None, settlement=False):
    cfg_ref, cfg, contract, bridge, adapter, runtime = ctx
    args = (operation_ref,) if request is None else (operation_ref, request)
    operation, legacy_cfg, binding = adapter.validate_operation_adoption(*args, settlement=settlement)
    entry.require(operation['config'] == cfg['legacy_config']
                  and legacy_cfg == entry.read(cfg['legacy_config']), 'EXACT_LEGACY_CONFIG_REQUIRED')
    entry.require(operation['request'] == contract['original_request'], 'ORIGINAL_QUESTION_PIN_REQUIRED')
    for key in ('task_id', 'account_key', 'notebook_id', 'budget_root', 'resource_root', 'query_budget'):
        entry.require(legacy_cfg.get(key) == contract.get(key), 'ORIGINAL_LEGACY_POLICY_CHANGED:' + key)
    entry.require(legacy_cfg['proxy'] == cfg['proxy']
                  and legacy_cfg['original_submit_lock'] == contract['original_submit_lock']
                  and legacy_cfg['limits'] == contract['limits'], 'ORIGINAL_LOCK_LIMITS_APPROVED_PROXY_REQUIRED')
    broker = contract['broker_module']
    alias = contract['original_controller_alias']
    entry.require(legacy_cfg['original_controller'] == binding['broker_module'] == alias
                  and entry.ref(alias['path']) == broker and alias['sha256'] == broker['sha256']
                  and binding['resource_root'] == contract['resource_root'], 'ORIGINAL_CONTROLLER_REQUIRED')
    command = [cfg['python']['path'], '-BE', str(Path(entry.__file__).resolve()), 'legacy-transport',
               '--config', cfg_ref['path'], '--config-sha256', cfg_ref['sha256'], '--output-dir', '{output_dir}']
    entry.require(binding['commands'].get('query') == command
                  and cfg_ref in binding['transport_artifacts'], 'CONTROLLED_INTERNAL_CHILD_REQUIRED')
    raw = entry.read(contract['original_request'])
    entry.require(raw.get('operation') == 'query' and raw.get('task_id') == cfg['task_id']
                  and raw.get('notebook_id') == cfg['notebook_id'] and bool(raw.get('prompt', '').strip())
                  and bool(raw.get('source_ids')) and len(set(raw['source_ids'])) == len(raw['source_ids']),
                  'EXACT_ORIGINAL_QUERY_SCOPE_REQUIRED')
    expected = {**raw, 'execution_adoption': operation_ref, 'account_key': cfg['account_key'],
                'notebook_id': cfg['notebook_id'], 'transport_contract': adapter.S.transport_contract(binding)}
    key = runtime.request_key(expected)
    entry.require(key not in contract['superseded_unsubmitted_keys'], 'SUPERSEDED_KEY_CANNOT_EXECUTE')
    if request is not None: entry.require(request == expected, 'EXACT_ORIGINAL_RECEIPT_REQUEST_REQUIRED')
    return operation, legacy_cfg, binding, expected, key


def explicit_guard(entry, config_path, request_path):
    # 安装权威从物理release导出；不接受任务选择的registry或“已检查”布尔。
    path = entry.SCRIPTS.parent.parent / 'NLM-GUARD-REGISTRY-PIN.json'
    authority = json.loads(path.read_text())
    entry.require(authority.get('schema') == 'nlm-network-entry-registry-authority-v1', 'GUARD_REGISTRY_AUTHORITY_REQUIRED')
    registry = authority['registry']; entry.checked(registry)
    from nlm_network_guard import event_check, load_registry
    argv = list(sys.orig_argv)
    entry.require(len(argv) == 8 and argv[1] == '-BE'
                  and Path(argv[2]).resolve() == Path(entry.__file__).resolve()
                  and argv[3] == 'legacy-run'
                  and dict(zip(argv[4::2], argv[5::2])) == {'--config': str(config_path), '--request': str(request_path)},
                  'ACTUAL_LEGACY_PUBLIC_INVOCATION_REQUIRED')
    event_check({'tool_name': 'exec_command', 'tool_input': {'cmd': shlex.join(argv)}},
                lambda: load_registry(registry['path'], registry['sha256']))
    return {'status': 'EXPLICIT_SAME_RELEASE_GUARD_ALLOW', 'registry': registry,
            'automatic_client_hook_observed': False, 'query_credit': False}


def decision(entry, ctx, spec, cfg_ref, key):
    _, cfg, contract, _, _, _ = ctx
    value = entry.read(spec['recovery_decision'])
    expected = {'schema': 'nlm-named-legacy-run-adoption-v1', 'status': 'ADOPTED_ONE_ORIGINAL_QUESTION',
                'task_id': cfg['task_id'], 'account_key': cfg['account_key'], 'notebook_id': cfg['notebook_id'],
                'supervisor_session': cfg['actor']['thread_id'], 'config': cfg_ref,
                'legacy_contract': cfg['legacy_contract'], 'request': contract['original_request'],
                'prepared': spec['prepared'], 'binding': spec['binding'], 'operation_adoption': spec['operation_adoption'],
                'request_key': key, 'query_cap': 1, 'automatic_retry': False, 'prior_attempts_preserved': True}
    entry.require(all(value.get(k) == v for k, v in expected.items()), 'EXACT_NEW_KEY_ROOT_ADOPTION_REQUIRED')
    return value


def local_validation_limit(entry, config_path):
    # 本地旧Consumer可能超过SDK30秒；上限只取安装批准的静态contract。
    with entry.phase_deadline(entry.PREFLIGHT_SECONDS, 'LEGACY_POLICY_PREFLIGHT_30_SECONDS'):
        cfg = entry.read(entry.ref(config_path)); policy = entry.enforce_route_policy(cfg)
        entry.require(cfg.get('legacy_contract') in policy.get('legacy_contracts', []), 'REGISTERED_LEGACY_CONTRACT_REQUIRED')
        contract = entry.read(cfg['legacy_contract'])
        entry.require(contract.get('schema') == 'nlm-legacy-task-contract-v1'
                      and contract.get('status') == 'APPROVED_STATIC_LEGACY_CONTRACT', 'APPROVED_STATIC_CONTRACT_REQUIRED')
        seconds = contract.get('local_validation_seconds')
        entry.require(type(seconds) is int and 0 < seconds <= 120, 'BOUNDED_APPROVED_LOCAL_VALIDATION_REQUIRED')
        return seconds


def run(entry, config_path, request_path):
    seconds = local_validation_limit(entry, config_path)
    with entry.phase_deadline(seconds, 'LEGACY_LOCAL_VALIDATION_DEADLINE'):
        ctx = context(entry, config_path); cfg_ref, cfg, contract, bridge, adapter, runtime = ctx
        guard = explicit_guard(entry, config_path, request_path)
        spec_ref = entry.ref(request_path); spec = entry.read(spec_ref)
        entry.require(spec.get('schema') == 'nlm-legacy-run-spec-v1' and spec.get('config') == cfg_ref,
                      'EXACT_POST_PREPARATION_RUN_SPEC_REQUIRED')
        operation, legacy_cfg, binding, expected, key = metadata(entry, ctx, spec['operation_adoption'])
        prepared = entry.read(spec['prepared'])
        entry.require(spec['binding'] == operation['binding'] and entry.read(spec['binding']) == binding
                      and prepared['binding'] == spec['binding'] and prepared['config'] == cfg['legacy_config']
                      and spec['request_key'] == key, 'ACTUAL_PREPARED_METADATA_REQUIRED')
        decision(entry, ctx, spec, cfg_ref, key)
        output = Path(spec['execution_output'])
        entry.require(output.is_absolute() and output.parent == Path(contract['adapter']['path']).parent
                      and not output.exists(), 'NEW_EXACT_EXECUTION_OUTPUT_REQUIRED')
        cls = bridge.private_budget(adapter, cfg, spec, runtime)
        entry.require(issubclass(cls, runtime.Budget) and cls.admit.__code__ is runtime.Budget.admit.__code__,
                      'ORIGINAL_BUDGET_CODE_REQUIRED')
    original_run, original_admit, original_history = runtime.run_bound, runtime.Budget.admit, runtime.verified_prior

    def run_bound(actual_binding, actual_request, budget):
        entry.require(actual_binding == binding and actual_request == {**entry.read(contract['original_request']),
                          'execution_adoption': spec['operation_adoption']}, 'EXACT_ORIGINAL_RUN_BOUND_INPUTS_REQUIRED')
        entry.require(type(budget) is cls and budget.root == Path(contract['budget_root']), 'EXACT_PRIVATE_ORIGINAL_BUDGET_REQUIRED')
        entry.enforce_route_policy(cfg); entry.actor_check(cfg)
        with entry.phase_deadline(entry.PREFLIGHT_SECONDS, 'LEGACY_PRE_ADMISSION_ROUTE_30_SECONDS'):
            route = entry.check_route(cfg, 'legacy_pre_admission')
        adapter.B.save(output / 'MANDATORY-ROUTE-PRE-ADMISSION.json', route)
        adapter.B.save(output / 'EXPLICIT-NETWORK-GUARD.json', guard)
        # 原run_bound仍独占原Broker/FIFO/BEGIN IMMEDIATE/计次和回执。
        return original_run(actual_binding, actual_request, budget)

    proxy = types.SimpleNamespace(Budget=cls, run_bound=run_bound)
    adapter.Q.E.reconciliation()
    def original_validator(*args, **kwargs):
        # 原execute会独立再校验；限定这一段，不把原240秒query包入本地时限。
        with entry.phase_deadline(seconds, 'LEGACY_ORIGINAL_ENTRY_VALIDATION_DEADLINE'):
            return adapter.validate_operation_adoption(*args, **kwargs)
    original_execute = adapter.B.derive(adapter.original, 'execute', [('out.parent==HERE', 'out.parent==ADAPTER_DIR')],
        {'ADAPTER_DIR': output.parent, 'validate_operation_adoption': original_validator,
         'legacy_runtime': lambda: proxy})
    try:
        return original_execute(spec['operation_adoption'], output)
    finally:
        entry.require(runtime.run_bound is original_run and runtime.Budget.admit is original_admit
                      and runtime.verified_prior is original_history, 'SHARED_LEGACY_RUNTIME_MUTATED')


def transport(entry, config_path, expected_sha256, output, *, lookup_original=False):
    entry.require(entry.ref(config_path)['sha256'] == expected_sha256, 'LEGACY_CHILD_CONFIG_CHANGED')
    ctx = context(entry, config_path); cfg_ref, cfg, contract, bridge, adapter, runtime = ctx
    folder = Path(output).resolve(strict=True)
    entry.require(folder.parent == Path(contract['budget_root']).resolve() / 'receipts', 'ORIGINAL_RECEIPT_DIRECTORY_REQUIRED')
    request = json.loads((folder / 'request.json').read_text())
    calls, validations = [], []

    def validate_operation(operation_ref, actual_request=None, *, settlement=False):
        # 原main在创建Clock和核lease之后调用这里；不把旧Consumer搬到240秒之外。
        entry.require(operation_ref == request['execution_adoption'] and actual_request == request
                      and settlement == lookup_original, 'EXACT_ORIGINAL_CHILD_VALIDATION_REQUIRED')
        operation, legacy_cfg, binding, _, key = metadata(entry, ctx, operation_ref,
            request=actual_request, settlement=settlement)
        entry.require(key == folder.name, 'ORIGINAL_RECEIPT_KEY_REQUIRED')
        validations.append(key)
        return operation, legacy_cfg, binding

    def before_send(host):
        # 私有桥在原Clock创建之后、真正send之前调用；同一进程，不重起计时。
        entry.require(validations == [folder.name], 'ORIGINAL_CLOCK_SCOPED_VALIDATION_REQUIRED')
        entry.enforce_route_policy(cfg); entry.actor_check(cfg)
        phase = 'legacy_original_lookup_send' if lookup_original else 'legacy_query_send'
        route = entry.check_route(cfg, phase, host=host)
        root = folder / 'result-check' if lookup_original else folder
        adapter.B.save(root / ('MANDATORY-ROUTE-SEND-' + str(time.time_ns()) + '.json'), route)
        calls.append(route)

    module = bridge.configure_child(adapter, cfg, before_send, validate_operation=validate_operation)
    argv = [module.__file__, str(folder), '--config', cfg['legacy_config']['path'],
            '--config-sha256', cfg['legacy_config']['sha256']]
    if lookup_original: argv.append('--lookup-original')
    old_argv = sys.argv
    try:
        sys.argv = argv
        # 同broker直接子进程调用；原require_lease的PID==PGID与原Clock不变。
        result = module.main()
        entry.require(result != 0 or (bool(calls) and validations == [folder.name]), 'SUCCESS_WITHOUT_MANDATORY_SEND_GATE')
        return result
    finally:
        sys.argv = old_argv
