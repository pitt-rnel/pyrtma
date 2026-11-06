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
| `test_deliver_skips_messages_that_do_not_match` | Test infrastructure: `deliver()` with `match` skips earlier messages of the same type that fail it, such as a stale resend. | Leaves a stale `TEST_START` with ID 0 queued before delivering one with ID 7. |
| `test_raw_connection_reaches_manager` | Test infrastructure: `raw_connection` is a plain socket connected to the `manager` fixture's port. | Compares the socket's peer port with the manager's port. |
| `test_collector_catches_thread_exception` | Test infrastructure: an exception escaping a thread is collected with its thread name, type, and traceback. | A thread that raises `RuntimeError`; the test takes the exception from the `thread_exceptions` fixture so teardown doesn't fail. |
| `test_manager_harness_reports_dead_thread` | Test infrastructure: a manager thread that dies is reported when the harness stops. | Sets an invalid `select()` timeout on a running manager, waits for the thread to die, and expects `HarnessError` naming `TypeError`. |

## test_manager.py — the message manager (needs: integration)

Tests that route real messages use the `manager` fixture, a raw socket from `raw_connection` whose headers carry `src_mod_id` 123, and `watcher()`. `watcher()` connects a sender and an observer that subscribes to `GOODBYE`, then to `TEST_START`. It then resends `TEST_START` with `deliver()` until it arrives, which shows the earlier subscriptions are in place. Tests that need conditions real sockets can't produce on demand drive a constructed, never-run manager (`bare_manager`) with `FakeConnection` stand-ins, which behave like non-blocking sockets. A fake records what each `send()` call takes; `accept` limits how many more bytes it takes, so a send can be partial, and a full or unwritable fake raises `BlockingIOError`. A failing fake raises `ConnectionResetError` like a reset peer. Bytes given to `feed()` are returned by `recv_into` no more than asked for at a time, an empty chunk reads as the peer closing, and with nothing fed it raises `BlockingIOError`. Every fake raises `OSError(EBADF)` after it's closed, like a real socket, and none has `sendall`, so the manager can't block on one. `read_once()` gives a fake module one read turn, as `run()` does when its socket is readable. The `manager_options` marker passes options such as `stall_timeout` to both `manager` and `bare_manager`.

### TestConstructor

| Test | Purpose | Approach |
|---|---|---|
| `test_options_after_port_are_keyword_only` | Timecode removal: `MessageManager` arguments after `port` are keyword-only, so an old positional call that passed `timecode` fails instead of shifting `log_level`. | Passes a log level as the third positional argument. |
| `test_timecode_argument_is_rejected` | Timecode removal: `MessageManager` no longer accepts `timecode`. | Passes `timecode=True` and expects a `TypeError` naming it. |
| `test_default_timeouts` | C1: by default a client stalled mid-message is dropped after 5 s, and logger modules are waited for without a limit. | Reads both settings from a default manager. |
| `test_timeouts_must_be_positive` | C1: a stall or logger timeout of zero or less is rejected, with an error naming the option. | Parametrized over both options and 0 and -1. |

### TestHeaderValidation

| Test | Purpose | Approach |
|---|---|---|
| `test_invalid_data_size_drops_only_that_client` | C2: a header announcing a negative or oversized payload drops that client with an error naming the size, and the manager keeps routing for the others. | Parametrized over -1 and 1 MiB + 1; a raw header, then the manager closing the raw socket, a fresh `TEST_START`, and the log record. |
| `test_core_message_with_wrong_size_drops_client` | C2: a core message whose `num_data_bytes` doesn't match its core definition drops the client with an error naming the type, isn't forwarded, and leaves the manager routing. | Parametrized over `SUBSCRIBE` with 0 bytes, `CONNECT_V2` with 4, and `DATASET_START` with 31; once the manager closes the raw socket, the observer, which also subscribes to the type, reads up to a marker `TEST_START` and must not have been sent the raw socket's message. |
| `test_core_message_with_right_size_is_forwarded` | C2: the core size check doesn't reject a correctly sized core message that the manager only forwards. | The raw socket connects, then two `DATASET_START`s of 32 bytes both reach the observer, so the first didn't drop it. |

### TestRemoval

| Test | Purpose | Approach |
|---|---|---|
| `test_simultaneous_subscriber_resets_remove_each_once` | C3: two subscribers whose connections reset during one forward are each closed once and announced by one `GOODBYE`, without a send to a closed socket escaping. | Two failing fakes subscribed to `ALL_MESSAGE_TYPES` and a healthy observer; one `forward_message` call. |
| `test_simultaneous_logger_resets_remove_each_once` | C3: two logger modules whose connections reset while being sent an ACK are each removed once, without the logger set changing under its own loop. | Two failing logger fakes; one `send_ack` call to a healthy module. |
| `test_remove_module_twice_is_harmless` | C3: removing a module twice raises nothing, closes it once, sends one `GOODBYE`, and leaves it in no routing table. | Calls `remove_module` twice on a fake. |
| `test_disconnected_client_leaves_sockets_list` | Low: the manager's `sockets` list drops a module's socket when it disconnects. | A factory client connects, then disconnects; waits until only the listening socket is left. |

### TestRouting

| Test | Purpose | Approach |
|---|---|---|
| `test_non_destination_module_is_not_counted_as_drop` | Manager routing: a subscriber that isn't the destination of a directed message gets no drop and causes no `FAILED_MESSAGE`, even when it isn't writable. | A directed message to one writable fake, with an unwritable bystander and a `FAILED_MESSAGE` observer. |
| `test_unwritable_destination_is_counted_as_drop` | Manager routing: an unwritable destination is still counted as a drop and reported with `FAILED_MESSAGE`. | A directed message to an unwritable fake; decodes the observer's `FAILED_MESSAGE`. |

### TestMsgCount

| Test | Purpose | Approach |
|---|---|---|
| `test_forwarded_message_keeps_sender_msg_count` | Manager routing: forwarded messages carry the sender's `msg_count`, not one per recipient. | Two `TEST_END` sends; compares the received counts with the sender's `msg_count` before each send. |
| `test_manager_messages_have_zero_msg_count` | Manager routing: messages that originate from the manager carry `msg_count` 0, while `Module.msg_count` still counts what each module was sent. | A fake with a count of 5 is sent an ACK, a `HELLO`, and a `FAILED_MESSAGE`. |
| `test_failed_message_reports_sender_msg_count` | Manager routing: `FAILED_MESSAGE` reports the sender's `msg_count`, not the count of a module sent the message before the failure. | An ordered list of subscribers in place of the set: a writable fake with a count of 40, then an unwritable one. |

### TestRunLoop

| Test | Purpose | Approach |
|---|---|---|
| `test_unexpected_error_drops_only_that_client` | C2: an unexpected exception while handling one client's message is logged with its traceback and drops that client, and `run()` keeps going. | Patches the manager's `register_module_ready` to raise; a client sends `MODULE_READY`; the observer sees its `GOODBYE` and still gets `TEST_START`. |

### TestReceiveBuffering

| Test | Purpose | Approach |
|---|---|---|
| `test_message_split_at_every_byte_is_reassembled` | C1: a message that arrives a byte at a time is put back together, header and payload, without a turn ever completing it early. | Feeds a 24-byte message in 1-byte chunks; every turn but the last completes nothing. |
| `test_back_to_back_messages_are_split_at_the_boundary` | C1: a read never takes more than the current message, so the next message's bytes stay unread and route to its own header and payload. | Two messages in one chunk; after the first turn, exactly the second message's bytes are left. |
| `test_interleaved_partial_messages_stay_separate` | C1: two clients' partial messages, read in alternation, each keep their own bytes. | Feeds two fakes their messages in pieces, alternating turns between them. |
| `test_spurious_readiness_keeps_client` | C1: a turn that finds nothing to read, as when `select()` reported readiness wrongly, ends quietly and keeps the client. | A fake with nothing fed. |
| `test_closed_connection_drops_client` | C1: a client that closes its connection is dropped with a warning and a `GOODBYE`, which says how many bytes had arrived when it closed mid-message. | Parametrized over a close at a message boundary and one 20 bytes into a header. |

### TestStalls

| Test | Purpose | Approach |
|---|---|---|
| `test_partial_message_does_not_block_other_clients` | C1: a client that stops partway through a message doesn't stop other clients from connecting and exchanging messages. | Parametrized over half a header, and a header without its payload, sent by a raw socket before the other clients connect. |
| `test_stalled_client_is_dropped_after_stall_timeout` | C1: a client stalled mid-message is dropped, no sooner than the stall timeout, with a warning giving the bytes received, and the manager keeps routing. | A 0.3 s timeout; a raw header announcing 16 bytes that never come; times the manager closing the raw socket. |
| `test_stall_sweep_drops_only_past_the_limit` | C1: the stall check drops a client only once the timeout has passed since its last bytes, and never drops one that isn't mid-message. | A 2 s timeout; runs the check with clock readings just under and just over it, with an idle module alongside. |
| `test_no_stall_timeout_keeps_stalled_client` | C1: with no stall timeout, a stalled client is never dropped. | Runs the check with a clock reading far in the future. |

### TestSending

| Test | Purpose | Approach |
|---|---|---|
| `test_message_is_sent_as_one_buffer` | P2: a forwarded message's header and payload go out in one send, and the bytes are the same as before. | Compares the fake's list of sends with the header bytes followed by the payload. |
| `test_partial_send_is_finished_before_anything_else` | Manager routing: when a connection takes only part of a message, the rest is sent first and nothing is interleaved, and a message forwarded meanwhile is counted as a drop with `FAILED_MESSAGE` instead. The module stays connected. | A fake that takes 60 bytes of a 148-byte message, then a second message, then room. |
| `test_remainder_is_finished_before_the_next_message` | Manager routing: once a connection has room again, the next forward finishes the queued remainder and then sends, with no drop. | As above, but the room comes before the second message. |
| `test_ack_waits_behind_a_remainder` | Manager routing: an ACK to a module with a remainder queued is sent after it instead of being dropped. | A partial message, then `send_ack`, then room. |
| `test_send_error_while_flushing_drops_module` | Manager routing: a connection that fails while its queued bytes are sent is dropped with a `GOODBYE`, and nothing escapes. | A partial message, then a fake that resets. |
| `test_slow_consumer_is_not_dropped` | Manager routing: a client that stops reading misses messages, reported with `FAILED_MESSAGE`, but stays connected; the manager keeps routing for others; and once the client reads again, its stream is whole. | Floods a non-reading subscriber with `TEST_MSG_8192` until a `FAILED_MESSAGE` names it, then drains it and delivers a marked message. |

### TestLoggers

| Test | Purpose | Approach |
|---|---|---|
| `test_logger_gets_whole_message_after_waiting` | Manager routing: by default the manager waits for a logger module that can't take a message, with no limit, and the logger gets the whole message. | A logger fake that takes 10 bytes; the patched wait records its timeout and makes room. |
| `test_logger_timeout_drops_hung_logger` | Manager routing: with a logger timeout, a logger that can't take a message within it is dropped with an error, a `FAILED_MESSAGE` and then a `GOODBYE`, and other modules still get the message. | A 0.25 s timeout; an unwritable logger fake; the patched wait times out. |
| `test_hung_logger_is_dropped_after_logger_timeout` | Manager routing: a real logger client that stops reading is dropped after the logger timeout, and the manager keeps routing. | A 0.5 s timeout; floods `TEST_MSG_8192` until the `GOODBYE` for the logger arrives. |

### TestAccept

| Test | Purpose | Approach |
|---|---|---|
| `test_accepted_connections_are_non_blocking` | C1: the manager makes every accepted connection non-blocking itself, rather than relying on what the operating system passes on from the listening socket. | Finds a connected client's socket in the manager's modules. |

### TestCommandLine

| Test | Purpose | Approach |
|---|---|---|
| `test_stall_timeout_options` | C1: `--stall-timeout` sets the stall timeout, `--no-stall-timeout` turns it off, and it defaults to 5 s. | Parametrized over no option, `--stall-timeout 2.5` and `--no-stall-timeout`. |
| `test_logger_timeout_option` | Manager routing: `--logger-timeout` sets the logger timeout, which defaults to none. | Parametrized over no option and `--logger-timeout 3`. |
| `test_invalid_timeout_options_are_rejected` | C1: the two stall options together, a timeout of zero or less, and a value that isn't a number are rejected. | Parametrized; each exits with a usage error. |

### TestDropLogging

| Test | Purpose | Approach |
|---|---|---|
| `test_dropped_client_is_not_sent_its_drop_warning` | C1: a client dropped for closing its connection or stalling isn't sent the warning about its own drop, and other modules get the warning before the `GOODBYE`. | Parametrized over both causes; the dropped fake and the observer subscribe to `RTMA_LOG_WARNING`. |

### TestConnect

| Test | Purpose | Approach |
|---|---|---|
| `test_rejected_module_id_sends_no_goodbye` | Manager introductions: a client refused because its static module ID is in use gets no `GOODBYE`, so nothing suggests the module already holding that ID left, and that module stays connected. | A second client asking for ID 50; then a marker client connects and disconnects, and the observer must see no `GOODBYE` for 50 before the marker's. |
| `test_rejected_module_id_is_not_kept` | Manager introductions: a refused module doesn't keep the ID it asked for, and is removed without a `GOODBYE`. Manager, second pass: the first dynamic ID can't be taken as a static one. | Parametrized over an ID already in use, one out of range, and `DYN_MOD_ID_START`; drives `connect_module` with a `CONNECT_V2`. |
| `test_only_connected_modules_get_a_goodbye` | Manager introductions: removing a socket that never connected closes it without a `GOODBYE`, while a connected module still gets one. | Removes one of each. |

### TestIntroductions

| Test | Purpose | Approach |
|---|---|---|
| `test_introductions_list_only_connected_modules` | Manager introductions: the reply to `INTRODUCE` has a HELLO for each connected module, the requester included, and none for the manager itself or for sockets that haven't connected. | A requester, another module and an accepted-only socket, besides the manager's own entry. |
| `test_failed_logger_send_during_introductions` | Manager introductions: a logger whose send fails partway through the reply is dropped, and the reply still reaches the requester in full, instead of failing with "dictionary changed size during iteration". | A logger fake that resets on its first HELLO copy. |
| `test_failed_requester_send_during_introductions` | Manager introductions: a requester whose send fails is dropped with a `GOODBYE`, and the introductions stop without an error. | A requester fake that resets. |

### TestConnectRequired

| Test | Purpose | Approach |
|---|---|---|
| `test_messages_before_connect_drop_the_socket` | Manager, second pass: a socket that sends anything but `CONNECT` first is dropped with a warning, and nothing it sent is acted on or forwarded, including the HELLO that `MODULE_READY` would trigger. | Parametrized over `SUBSCRIBE`, a user message and `MODULE_READY` from a raw socket; the observer reads up to a marker after the manager closes it. |
| `test_hello_is_not_sent_for_a_socket_that_never_connected` | Manager, second pass: `send_hello` sends nothing for a module that hasn't connected. | Calls it for an accepted-only fake. |

### TestForwardingAfterDrop

| Test | Purpose | Approach |
|---|---|---|
| `test_refused_connect_is_not_forwarded` | Manager, second pass: a `CONNECT` refused for a duplicate ID isn't passed on to subscribers. | A `CONNECT_V2` asking for ID 50, which another module holds; the observer subscribes to `CONNECT_V2`. |
| `test_disconnect_is_still_forwarded` | Manager, second pass: `DISCONNECT` is still passed on, although handling it drops its sender. | The observer subscribes to `DISCONNECT`. |

### TestAcknowledgements

| Test | Purpose | Approach |
|---|---|---|
| `test_logger_gets_one_ack_per_request` | Manager, second pass: a logger that makes a request gets one ACK for it, while other loggers still get their copy. | Two logger fakes subscribed to everything; one sends `SUBSCRIBE`. |

### TestSubscriptionTable

| Test | Purpose | Approach |
|---|---|---|
| `test_forwarding_adds_no_entries` | Manager, second pass: forwarding messages of types nobody subscribes to adds nothing to the subscription table. | Forwards 100 distinct types. |
| `test_unsubscribed_types_leave_no_entries` | Manager, second pass: a type is removed from the table when its last subscriber unsubscribes or is removed. | Subscribes and unsubscribes one type, subscribes to another, then removes the module. |

### TestStaticIds

| Test | Purpose | Approach |
|---|---|---|
| `test_highest_static_id_is_accepted` | Manager, second pass: the ID just below the dynamic range is still accepted as a static ID. | `connect_module` with `DYN_MOD_ID_START - 1`. |

### TestSelectLimits

| Test | Purpose | Approach |
|---|---|---|
| `test_limits_follow_the_platform` | Manager, second pass: the manager refuses connections past 512 sockets on Windows and past descriptor 1023 elsewhere, which are the limits of `select()`. | Reads both limits. |
| `test_connection_beyond_socket_limit_is_refused` | Manager, second pass: a connection beyond the socket limit is closed with a warning, and the manager keeps routing. | Lowers the limit to the three sockets already open, then connects a raw socket. |
| `test_connection_with_high_descriptor_is_refused` | Manager, second pass: a connection whose descriptor `select()` can't watch is closed with a warning, instead of `select()` raising and stopping the manager. POSIX only. | Holds open descriptors until new ones are numbered above 1100, then connects a raw socket. |
| `test_listening_socket_with_high_descriptor_raises` | Manager, second pass: a manager whose listening socket would be beyond the descriptor limit fails at construction with a clear error. POSIX only. | Constructs a manager while descriptors above 1100 are held open. |

### TestModuleLimit

| Test | Purpose | Approach |
|---|---|---|
| `test_limit_is_max_modules` | Manager, second pass: at most `MAX_MODULES` (256) modules may be connected at once. | Reads the limit. |
| `test_manager_and_unconnected_sockets_do_not_count` | Manager, second pass: the manager's own entry and sockets that haven't connected don't count toward the limit. | A limit of 1, with an accepted-only fake besides the manager's entry. |
| `test_connect_beyond_the_limit_is_refused` | Manager, second pass: a `CONNECT` beyond the limit is refused with an error naming it, the manager keeps routing, and a module can connect again once another leaves. | Lowers the limit to the two connected clients, then connects a third, disconnects one and connects again. |

## test_client.py — the client's constructor and context manager (needs: none)

| Test | Purpose | Approach |
|---|---|---|
| `test_options_after_host_id_are_keyword_only` | Timecode removal: `Client` and `client_context` arguments after `host_id` are keyword-only, so an old positional call that passed `timecode` fails instead of shifting the arguments after it. | Parametrized over both; a third positional argument for `Client`, a fifth for `client_context`. |
| `test_timecode_argument_is_rejected` | Timecode removal: `Client` and `client_context` no longer accept `timecode`. | Parametrized over both; passes `timecode=True` and expects a `TypeError` naming it. |

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

`wire_format_snapshot.json` records the 4.0.0 wire format, less the timecode header, which Phase 2 removed by decision. Layouts are written as `name:type@offset`, with types named by kind and size, such as `int64`, so the snapshot is the same on Linux and Windows. The snapshot is never edited to make a change pass.

| Test | Purpose | Approach |
|---|---|---|
| `test_get_header_cls_returns_the_only_header` | Timecode removal: `get_header_cls()` takes no argument and returns `MessageHeader`, the only header class. | Calls it and compares the class. |
| `test_header_matches_snapshot` | Test infrastructure: the message header's size and field layout are unchanged, and it is the only header. | Compares the whole `headers` section with the snapshot. |
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
