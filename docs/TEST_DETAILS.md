# pyrtma — Test catalogue

**Claude:** read `docs/WORKFLOW.md` first, then `docs/PROGRESS.md`, and follow the stage its **Next** line names.

Run with `pytest -v`. `tests/test_docs.py` checks that this file lists every test function, and nothing else.

The layout:

- One `##` heading per test file: `## test_<module>.py — <what it covers> (needs: <markers or tools, or none>)`.
- Optionally, a paragraph on setup that the file's tests share.
- A table for the test functions outside classes, right under the file's heading, then a `###` heading for each test class, named as in the code, with its own table.
- One row per test function: `| Test | Purpose | Approach |`. Purpose says what behavior the test pins down; Approach says how, such as the input or the stand-in it uses. Parametrized cases share their function's row.

## test_docs.py — this catalogue (needs: none)

| Test | Purpose | Approach |
|---|---|---|
| `test_every_test_is_catalogued` | This file lists every test function in `tests/`, and has no entries for tests that no longer exist. | Compares the names found by `ast` with the names in the tables here. |
| `test_catalogue_names_follow_headings` | A row is named by its file heading, plus its class heading when it has one; other sections and other tables are ignored. | A small catalogue with a module-level row, a class row, and an unrelated table. |
| `test_collected_tests_include_class_methods` | Test functions are found at module level and inside `Test` classes, and nowhere else. | A test file in `tmp_path` with a helper, a test, a test class, and a non-test class. |

## test_harness.py — the shared fixtures in `conftest.py` and `helpers.py` (needs: integration)

| Test | Purpose | Approach |
|---|---|---|
| `test_free_port_can_be_bound` | Test infrastructure: `free_port` returns a loopback port that can actually be bound. | Binds a socket to the port from the fixture. |
| `test_manager_routes_between_clients` | Test infrastructure: the `manager` and `client_factory` fixtures give clients that can subscribe and receive. | Two factory clients; `deliver()` resends `TEST_START` until the subscriber reads it, then compares the payload. |
| `test_raw_connection_reaches_manager` | Test infrastructure: `raw_connection` is a plain socket connected to the `manager` fixture's port. | Compares the socket's peer port with the manager's port. |
| `test_collector_catches_thread_exception` | Test infrastructure: an exception escaping a thread is collected with its thread name, type, and traceback. | A thread that raises `RuntimeError`; the test takes the exception from the `thread_exceptions` fixture so teardown doesn't fail. |
| `test_manager_harness_reports_dead_thread` | Test infrastructure: a manager thread that dies is reported when the harness stops. | Sets an invalid `select()` timeout on a running manager, waits for the thread to die, and expects `HarnessError` naming `TypeError`. |

## test_integration.py — client and manager interaction (needs: loopback sockets; not yet marked)

Each test starts a `MessageManager` on an unused loopback port in `setUp` and connects one client with module ID 11 or 12. `wait_for_message()` is a fixed short sleep. Two message types defined in the file, `TEST_MESSAGE` and `TEST_MESSAGE2`, are used for subscriptions.

### TestSingleClient

| Test | Purpose | Approach |
|---|---|---|
| `test_whenClientConnects_clientConnectsToMessageManager` | `connect()` marks the client connected and registers its module ID with the manager. | Checks `client.connected` and the manager's module list. |
| `test_whenClientSubscribes_clientIsSubscribedToMessageType` | `subscribe()` adds the client to the manager's subscribers for that type. | Inspects `manager.subscriptions`. |
| `test_whenClientSubscribesMulti_clientIsSubscribedToMessageTypes` | `subscribe()` with two types subscribes to both. | As above, for both types. |
| `test_whenClientUnsubscribes_clientIsUnsubscribedFromMessageType` | `unsubscribe()` removes the client from that type's subscribers. | Subscribes, unsubscribes, inspects `manager.subscriptions`. |
| `test_whenClientUnsubscribesMulti_clientIsUnsubscribedFromMessageTypes` | `unsubscribe()` with two types removes both. | As above, for both types. |
| `test_whenClientPauses_clientIsRemovedFromMessageType` | `pause_subscription()` removes the client from the manager's subscribers. | Subscribes, pauses, inspects `manager.subscriptions`. |
| `test_whenClientPausesMulti_clientIsRemovedFromMessageTypes` | Pausing two types removes both. | As above, for both types. |
| `test_whenClientResumes_clientIsAddedToMessageType` | `resume_subscription()` restores a paused subscription in the manager. | Subscribes, pauses, resumes, inspects `manager.subscriptions`. |
| `test_whenClientResumesMulti_clientIsAddedToMessageType` | Resuming two paused types restores both. | As above, for both types. |
| `test_whenClientContextSubscribes_clientIsSubscribedToMessageType` | Inside `subscription_context()`, the client is subscribed. | Checks `manager.subscriptions` inside the context. |
| `test_whenClientContextSubscribesMulti_clientIsSubscribedToMessageTypes` | `subscription_context()` with two types subscribes to both. | As above, for both types. |
| `test_whenClientContextUnsubscribes_clientIsUnsubscribedFromMessageType` | Leaving `subscription_context()` unsubscribes the client. | Checks `manager.subscriptions` after the context exits. |
| `test_whenClientContextUnsubscribesMulti_clientIsUnsubscribedFromMessageTypes` | Leaving a two-type `subscription_context()` unsubscribes both. | As above, for both types. |
| `test_whenClientContextPauses_clientIsRemovedFromMessageType` | Inside `paused_subscription_context()`, the subscription is paused at the manager. | Nested contexts; checks inside the inner one. |
| `test_whenClientContextPausesMulti_clientIsRemovedFromMessageTypes` | `paused_subscription_context()` with two types pauses both. | As above, for both types. |
| `test_whenClientContextResumes_clientIsAddedToMessageType` | Leaving `paused_subscription_context()` resumes the subscription. | Checks after the inner context exits, inside the outer one. |
| `test_whenClientContextResumesMulti_clientIsAddedToMessageType` | Leaving a two-type paused context resumes both. | As above, for both types. |

### TestSingleContextClient

| Test | Purpose | Approach |
|---|---|---|
| `test_whenClientConnects_clientConnectsToMessageManager` | `client_context()` yields a connected client registered with the manager. | Checks `client.connected` and the manager's module list inside the context. |
| `test_whenClientConnects_mod_id_is_correct` | `client_context()` keeps the requested module ID. | Compares `client.module_id` with module ID 12. |
| `test_whenClientContextSubscribes_clientIsSubscribedToMessageType` | `client_context(msg_list=...)` subscribes on entry. | Inspects `manager.subscriptions`. |
| `test_whenClientContextSubscribesMulti_clientIsSubscribedToMessageTypes` | `client_context()` with two types subscribes to both. | As above, for both types. |
| `test_whenClientContextUnsubscribes_clientIsUnsubscribedFromMessageType` | A `subscription_context()` inside `client_context()` unsubscribes on exit. | Checks `manager.subscriptions` after the inner context. |
| `test_whenClientContextUnsubscribesMulti_clientIsUnsubscribedFromMessageTypes` | As above, with two types. | As above, for both types. |
| `test_whenClientContextPauses_clientIsRemovedFromMessageType` | `paused_subscription_context()` pauses a subscription made by `client_context()`. | Checks `manager.subscriptions` inside the paused context. |
| `test_whenClientContextPausesMulti_clientIsRemovedFromMessageType` | As above, with two types. | As above, for both types. |
| `test_whenClientContextResumes_clientIsAddedToMessageType` | Leaving the paused context resumes a subscription made by `client_context()`. | Checks `manager.subscriptions` after the paused context. |
| `test_whenClientContextResumesMulti_clientIsAddedToMessageType` | As above, with two types. | As above, for both types. |

## test_encoding.py — message bytes through the manager (needs: loopback sockets; not yet marked)

### TestEncoding

| Test | Purpose | Approach |
|---|---|---|
| `test_message_encoding` | Every test-definition message with an ID above 1000 arrives byte-for-byte as sent. | A publisher sends `from_random()` data for each type to a subscriber through a manager on an unused port; messages compare by their bytes. |

## test_sync.py — definition mismatches between sender and receiver (needs: loopback sockets; not yet marked)

### TestSync

| Test | Purpose | Approach |
|---|---|---|
| `test_version_mismatch` | `read_message(sync_check=True)` raises `InvalidMessageDefinition` when the header's version doesn't match the receiver's definition. | Forwards a hand-built header with version `0xDEADBEEF`. |
| `test_size_mismatch` | `read_message(sync_check=True)` raises `InvalidMessageDefinition` when the payload size doesn't match. | Sends `TEST_METADATA` bytes under the `TEST_START` type. |

## test_json.py — dict and JSON round trips (needs: none)

### TestJSONConversion

| Test | Purpose | Approach |
|---|---|---|
| `test_dict` | `to_dict()` and `from_dict()` round-trip every test-definition message. | `from_random()` data for each type; compares fields, bytes, and the dicts. |
| `test_json` | `to_json()` and `from_json()` round-trip every test-definition message. | As above, comparing the JSON strings. |

## test_message_definitions.py — loading compiled definitions (needs: none)

### TestMessageDefinitions

| Test | Purpose | Approach |
|---|---|---|
| `test_core_defs_exposes_message_definitions` | `core_defs.get_message_definitions()` returns a `MessageDefinitions` that maps names, IDs, and classes. | Looks up `ACKNOWLEDGE` by name and by ID. |
| `test_load_message_definitions_from_core_file` | `load_message_definitions()` loads the core definitions file by path. | Loads `core_defs.py` and looks up `ACKNOWLEDGE`. |
| `test_load_legacy_message_definitions_file` | `load_message_definitions()` loads the compiled test definitions by path. | Loads `tests/test_msg_defs/test_defs.py`. Despite the name, that file defines `get_message_definitions()`, so the legacy fallback isn't exercised. |
| `test_dataset_uses_explicit_definitions_without_client` | `Dataset` resolves message names from definitions passed to it, without creating a client. | A `Dataset` with `create_client=False` and type 6000; expects `ALIAS_TEST`. |

## test_message_version.py — compiled definition versions (needs: none)

### TestMessageVersion

| Test | Purpose | Approach |
|---|---|---|
| `test_version` | The core, test, and example definitions were compiled with the installed pyrtma version. | Compares each file's `COMPILED_PYRTMA_VERSION` with `pyrtma.__version__`. |

## test_parser.py — YAML definition parser errors (needs: none)

Each test writes YAML to temporary files and expects `Parser.parse()` to raise a specific error, or to succeed.

### TestParser

| Test | Purpose | Approach |
|---|---|---|
| `test_host_id_conflicts` | Two hosts with the same ID raise `HostIDError`. | One file with hosts A and B both 10. |
| `test_module_id_conflicts` | Two modules with the same ID raise `ModuleIDError`. | One file with modules A and B both 10. |
| `test_signal_id_conflicts` | Two signals with the same ID raise `MessageIDError`. | Messages A and B with ID 100 and no fields. |
| `test_message_id_conflicts` | Two messages with the same ID raise `MessageIDError`. | Messages A and B with ID 100 and one field each. |
| `test_duplicate_message` | The same message defined in two files raises `DuplicateNameError`. | Parses the same YAML from two files with one parser. |
| `test_duplicate_module` | The same module defined in two files raises `DuplicateNameError`. | As above, for a module ID. |
| `test_duplicate_host` | The same host defined in two files raises `DuplicateNameError`. | As above, for a host ID. |
| `test_duplicate_constant` | The same constant defined in two files raises `DuplicateNameError`. | As above, for a constant. |
| `test_constant_name_conflicts` | A constant whose name is used by another kind of definition raises `DuplicateNameError`. | A constant against a string constant, alias, struct, and message of the same name. |
| `test_string_constant_name_conflicts` | A string constant whose name is used by another definition raises `DuplicateNameError`. | As above, starting from a string constant. |
| `test_alias_name_conflicts` | An alias whose name is used by another definition raises `DuplicateNameError`. | As above, starting from an alias. |
| `test_struct_name_conflicts` | A struct whose name is used by another definition raises `DuplicateNameError`. | As above, starting from a struct. |
| `test_message_name_conflicts` | A message whose name is used by another definition raises `DuplicateNameError`. | As above, starting from a message. |
| `test_yaml_syntax` | A duplicate YAML key raises `YAMLSyntaxError`. | `struct_defs` given twice in one file. |
| `test_rtma_syntax` | Names that break the RTMA naming rules, and illegal field names, raise `RTMASyntaxError`. | Several bad struct, message, and field names. |
| `test_type_error` | IDs of the wrong type raise `InvalidTypeError`. | A string given as a host ID and as a module ID. |
| `test_reserve_syntax` | Malformed `_RESERVED_` entries raise `RTMASyntaxError` or `InvalidTypeError`. | `_RESERVED_` given fields, a scalar, malformed ranges, and an ID. |
| `test_auto_padding` | Messages whose fields need alignment padding parse without error. | Messages mixing `char`, `int`, `double`, `float`, and `int64` fields, and one nesting the others. |
| `test_reserved_fields` | A field named with a reserved word raises `RTMASyntaxError`. | A field named `auto`. |
| `test_prefix_fields` | Field and constant names with a leading underscore or digit raise `RTMASyntaxError`. | `_bad_prefix` and `9bad_prefix` fields, and a `_bad_prefix` constant. |

## test_validators.py — field descriptors and validation (needs: none)

Uses the `VALIDATOR_A` and `VALIDATOR_B` messages from the test definitions, which have a field of every supported type.

### TestEncoding

| Test | Purpose | Approach |
|---|---|---|
| `test_validator_range` | Every numeric field accepts the minimum and maximum of its type. | Assigns the limits of each integer type and of float32. |
| `test_validator_out_of_range` | Every numeric field rejects values just outside its type's range with `ValueError`. | Assigns one past each limit. |
| `test_array_len` | Assigning an array of the wrong length raises `ValueError`. | Lists and ctypes arrays of length 5 into each array field. |
| `test_get_types` | Reading a field returns the documented Python type or array wrapper. | `isinstance` checks on every field of a fresh message. |
| `test_invalid_set_types` | Assigning a value of the wrong type raises `TypeError`. | Wrong Python and ctypes types into each field. |
| `test_valid_set_types` | Every field accepts its Python type and its ctypes type. | Assigns both forms to each field. |
| `test_refs` | Two message instances don't share field storage, and array wrappers are distinct objects. | Sets fields on one message, then compares values and identities with another. |

## test_wire_format.py — the frozen wire format (needs: none)

`wire_format_snapshot.json` records the 4.0.0 wire format. Layouts are written as `name:type@offset`, with types named by kind and size, such as `int64`, so the snapshot is the same on Linux and Windows. The snapshot is never edited to make a change pass.

| Test | Purpose | Approach |
|---|---|---|
| `test_header_matches_snapshot` | Test infrastructure: the message header's size and field layout, with and without timecode, are unchanged. | Parametrized over `timecode`; compares `get_header_cls()` with the snapshot. |
| `test_core_definitions_match_snapshot` | Test infrastructure: every core struct and message keeps its ID, type hash, size, and layout, and the core module and host IDs are unchanged; none are added or removed. | Parametrized over the snapshot's sections; lists each entry that differs. |
| `test_layout_names_types_by_size` | Test infrastructure: layout descriptions don't depend on which ctypes alias a platform uses. | A structure with `c_int64` and `c_longlong` fields, a char array, and a double array. |

## test_random_fields.py — values from `from_random()` (needs: none)

Each test fills a structure with one scalar field and one 8-element array field of the given type, 50 times, and checks every value drawn.

| Test | Purpose | Approach |
|---|---|---|
| `test_int64_values_use_full_range` | Test helpers: int64 fields get negative values and values beyond 32 bits, on every platform. | Parametrized over `c_int64` and `c_longlong`, which are different aliases on Linux and Windows. |
| `test_uint64_values_use_full_range` | Test helpers: uint64 fields get values beyond 32 bits. | Parametrized over `c_uint64` and `c_ulonglong`. |
| `test_int_values_stay_in_range` | Test helpers: every integer type gets values inside its own range, reaching its upper half. | Parametrized over each ctypes integer type and alias. |
| `test_float_values_include_negatives_and_large_values` | Test helpers: float and double fields get finite values, including negative ones and ones above 1. | Parametrized over `c_float` and `c_double`. |
