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
| `test_scripted_manager_connects_and_sends` | Test infrastructure: `ScriptedManager` connects a client with a dynamic ID, delivers what the test sends, and reads back what the client sent. | Connects a client, sends it a `TEST_START`, and reads the client's `SUBSCRIBE` back from the stand-in. |

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

### TestLateConnectV2

| Test | Purpose | Approach |
|---|---|---|
| `test_connect_v2_after_connect_updates_name_and_pid` | Manager connect messages: a `CONNECT_V2` from a connected module updates its name and process ID and sends one `HELLO` with them, without an ACK; the module keeps its ID. | A connected fake module sends `CONNECT_V2`; an observer subscribed to `HELLO`. |
| `test_connect_after_connect_v2_changes_nothing` | Manager connect messages: a `CONNECT` from a connected module changes nothing and sends nothing, even with a different logger status. | A connected fake module sends `CONNECT` with `logger_status` 1. |
| `test_late_connect_v2_keeps_id_and_logger_status` | Manager connect messages: a late `CONNECT_V2` asking for another module ID or logger status keeps the existing ones and logs a warning about each; the name is still taken. | A `CONNECT_V2` asking for ID 77 as a logger, with the manager logging at `WARNING` and `caplog` capturing. |
| `test_late_connect_v2_is_announced` | Manager connect messages: over a real connection, a `CONNECT` and then a `CONNECT_V2` give one ACK, then a `HELLO` with the name and process ID from the `CONNECT_V2`. | A raw socket, whose `CONNECT` asks for ID 123 through its header; an observer whose subscriptions are confirmed with `deliver()` first. |

### TestConnectNames

| Test | Purpose | Approach |
|---|---|---|
| `test_connect_with_a_name_that_is_not_ascii_is_dropped` | Strings, validation and logging: names must be ASCII, as decided in Phase 5. A `CONNECT_V2` whose name isn't ASCII drops that connection, and the manager keeps running. | A raw connection sends a `CONNECT_V2` with "Módulo" encoded as UTF-8 written straight into the name field; then a new client connects. |

## test_client.py — the client: signatures, receiving, sending, connecting, lost connections and subscriptions (needs: integration for every class)

Most receive tests use `scripted_client`, a client connected to the `scripted_manager` fixture: a stand-in manager (`helpers.ScriptedManager`) that ACKs the client's connect and then sends only the bytes the test gives it, built with `helpers.frame()`. It never ACKs subscriptions, so nothing reaches the client unless the test sends it. Tests wait for sent bytes to arrive with `wait_until_arrived()`, which peeks at the client's socket. A read that could block on a partial message runs under `watchdog()`, which resets the stand-in's connection after 3 s, so that the old code fails with `ConnectionLost` instead of hanging. Timing checks allow `SLACK`, 1 s, beyond the timeout. Type 7777 stands for a type the test definitions don't define.

`TestConnect` uses `HandshakeStandIn`, a listening socket that reads one client's connect message and then sends the bytes the test gives it, which may be nothing, so a test controls the ACKs the client sees.

`TestSubscriptions` uses the real `manager` fixture and `client_factory`, with types 7001 to 7005, of which nothing is ever sent. `manager_subscriptions()` returns the manager's own subscription set for a client, after a barrier: the client sends `CLIENT_SET_NAME` with a fresh name, and the manager handles each client's messages in order, so once the name has changed, every earlier subscription message has been handled. Each test checks the client's local state and the manager's.

| Test | Purpose | Approach |
|---|---|---|
| `test_options_after_host_id_are_keyword_only` | Timecode removal: `Client` and `client_context` arguments after `host_id` are keyword-only, so an old positional call that passed `timecode` fails instead of shifting the arguments after it. | Parametrized over both; a third positional argument for `Client`, a fifth for `client_context`. |
| `test_timecode_argument_is_rejected` | Timecode removal: `Client` and `client_context` no longer accept `timecode`. | Parametrized over both; passes `timecode=True` and expects a `TypeError` naming it. |
| `test_failed_constructor_leaves_no_unraisable_exception` | Client `__del__`: a `Client` whose constructor raises is collected without an exception from `__del__`. | Parametrized over module IDs -1 and 10000, both out of range; `sys.unraisablehook` is replaced to collect what `__del__` raises. |

### TestReceive

| Test | Purpose | Approach |
|---|---|---|
| `test_unsubscribed_stream_does_not_extend_timeout` | H2: messages the client isn't subscribed to use up the timeout rather than restarting it, so `read_message(0.3)` returns within it. | A thread has the stand-in send an ACK every 50 ms for 3 s; the client is subscribed to `TEST_START` only. |
| `test_partial_message_does_not_block_past_timeout` | C1 (client side): with part of a message received, `read_message` returns None within its timeout, including a timeout of 0. | Parametrized over a split in the header and in the payload, and timeouts 0 and 0.2 s; the rest is never sent. |
| `test_partial_message_completes_on_a_later_read` | C1 (client side): the bytes of a partial message are kept, and a later read returns the whole message. | Sends part of a `TEST_START`, reads with timeout 0, sends the rest, and reads again; parametrized over the same splits. |
| `test_blocking_read_waits_for_a_message` | C1 (client side): a timeout of None or -1 blocks until a message arrives. Already right before the fix. | A timer has the stand-in send a `TEST_START` after 0.2 s. |
| `test_poll_reads_at_most_one_message` | H2: a timeout of 0 reads at most one message and doesn't wait, as decided in the phase discussion: an ACK in front of a subscribed message gives None, and the next poll returns the message. Already right before the fix. | An ACK and a `TEST_START`, both arrived before the first read. |
| `test_unsubscribed_message_of_unknown_type_is_skipped` | Client receive: a message of an unknown type that the client isn't subscribed to is discarded without raising. | An unknown-type message, then a `TEST_START` the client is subscribed to. |
| `test_subscribed_message_of_unknown_type_raises` | Client receive: a subscribed message of an unknown type still raises `UnknownMessageType` with its raw payload, and the next message reads correctly. Already right before the fix. | Subscribes to the unknown type and `TEST_START`, and sends one of each. |
| `test_subscribed_message_of_wrong_size_raises` | Client receive: a subscribed message whose size doesn't match its definition still raises `InvalidMessageDefinition`, and the next message reads correctly. Already right before the fix. | A `TEST_START` with an 8-byte payload instead of 4, then a correct one. |
| `test_decode_errors_carry_the_header` | C5: `UnknownMessageType` and `InvalidMessageDefinition` raised while reading carry the message's header, so a data logger can tell which type it couldn't record. | Parametrized over a type the definitions don't have and a `TEST_START` of 8 bytes; checks `header.msg_type` on the exception. |
| `test_discard_messages_empties_the_queue` | H1: `discard_messages()` discards every message that has arrived, subscribed or not, of any type, and returns True. | Ten rounds of an ACK, a `TEST_START` and an unknown-type message; afterwards the socket must have nothing to read. |
| `test_discard_messages_reports_messages_left_at_its_timeout` | H1: `discard_messages()` returns False when its timeout ends with messages still waiting, and True once they're gone. | 200 ACKs; `discard_messages(timeout=0)`, then `discard_messages()`. |
| `test_reset_subscriptions_leaves_nothing_queued` | H1: `reset_subscriptions()` unsubscribes from everything and leaves nothing queued. | 25 rounds of an ACK and a `TEST_START`; the stand-in doesn't ACK the unsubscribes, so anything left was queued before the reset. |
| `test_lost_connection_marks_client_disconnected` | Client: a lost connection raises `ConnectionLost`, and leaves the client disconnected, its socket closed and its subscriptions cleared. | Parametrized: the stand-in closes cleanly, resets the connection, or closes partway through a message. |
| `test_send_after_reset_marks_client_disconnected` | Client: a send on a reset connection raises `ConnectionLost` and leaves the client disconnected with its socket closed. | Waits for the reset to reach the client's socket, then sends a `TEST_START`. |
| `test_corrupt_header_drops_the_connection` | Client receive: a header announcing a negative payload or one over 1 MiB raises `ConnectionLost` naming the size, and leaves the client disconnected. | Parametrized over -1 and 1 MiB + 1, with no payload sent. |
| `test_payload_limit_matches_the_manager` | Client receive: the client's 1 MiB payload limit is the manager's, so the client accepts any message the manager forwards. | Compares the tests' `MAX_DATA_BYTES` with the size of a running manager's receive buffer. |
| `test_reconnect_discards_partial_message` | C1 (client side): a reconnect forgets a partly received message, so it can't corrupt the first messages on the new connection, including the connect's ACK. | Part of a header from one stand-in, then a connect to a second stand-in that sends a `TEST_START`. |

### TestSend

| Test | Purpose | Approach |
|---|---|---|
| `test_signal_reaches_a_dynamically_assigned_module` | H4: `send_signal` to a module with a dynamic ID is sent and delivered, instead of raising `InvalidDestinationModule`. | Two `client_factory` clients; `LM_READY` is signalled to the receiver's assigned ID until it arrives. |
| `test_all_hosts_is_accepted` | H4: `send_message` and `send_signal` accept `ALL_HOSTS`, and the manager forwards the message instead of rejecting it. | Parametrized over both methods; resends `LM_READY` to `ALL_HOSTS` until the receiver reads it, and checks its header. |
| `test_invalid_destinations_are_rejected` | H4: both methods still reject module IDs below 0 or above `MAX_MODULE_ID`, and host IDs outside 0 to `MAX_HOSTS` other than `ALL_HOSTS`. | Parametrized over both methods and five destinations, including `ALL_HOSTS - 1`, on `scripted_client`. |
| `test_sends_report_success` | Client Low (silent dropped packet): the three send methods return `True` when they send. | `send_message`, `send_signal` with `timeout=0`, and `forward_message`, on `scripted_client`. |
| `test_unwritable_socket_reports_a_dropped_send` | Client Low (silent dropped packet): when the socket isn't writable within the timeout, each send method returns `False`, prints nothing, and the client stays connected. | A stand-in that never reads; `fill_send_buffer()` writes raw bytes to the client's socket until `select()` reports it unwritable, then each method is called with `timeout=0`. |
| `test_send_waits_for_room_in_the_socket` | Client receive: with the socket non-blocking, a send that finds the socket's buffer full waits and carries on, and every byte arrives in order. | A stand-in with a 4 KiB receive buffer and a client with a 4 KiB send buffer; a thread sends 4,000 `TEST_MSG_8192` messages, about 33 MB, while the stand-in reads them all, then each header and the payload's first byte are checked. Fails with a plain `sendall`. |

### TestConnect

| Test | Purpose | Approach |
|---|---|---|
| `test_unresolvable_host_raises_manager_not_found` | Client connection error handling: a host name that can't be resolved raises `MessageManagerNotFound`, not a raw `socket.gaierror`, and the client is left disconnected. | Connects to `no-such-host.invalid`, a name reserved never to resolve. |
| `test_refused_connection_raises_manager_not_found` | Client connection error handling: a refused connection raises `MessageManagerNotFound` and leaves the client disconnected. | Connects to the `free_port` fixture's port, where nothing listens. |
| `test_tcp_connect_is_bounded_by_the_timeout` | Client connection error handling: the TCP connect is given what is left of `connect()`'s timeout, and a connect that times out raises `MessageManagerNotFound`. | A `socket.socket` subclass, patched into `pyrtma.client`, whose `connect` records its socket's timeout and raises `TimeoutError`, as an unanswered connect does; loopback can't produce one. |
| `test_ack_timeout_raises_and_leaves_client_disconnected` | Client connection error handling: with no ACK, `connect()` raises `AcknowledgementTimeout` within its timeout, reports itself disconnected, and has closed its socket. | `HandshakeStandIn` that sends nothing; `timeout=0.3`. |
| `test_static_client_ignores_another_modules_ack` | Client ACK matching: a client with a static ID doesn't take an ACK addressed to another module, such as a copy a logger is sent. | The stand-in sends only an ACK for module 99 to a logger with ID 11; `connect()` must time out. |
| `test_static_client_takes_its_own_ack` | Client ACK matching: the client skips the other module's ACK, takes its own, and leaves nothing unread. | The stand-in sends an ACK for module 99, then one for 11; the socket must have nothing left to read. |
| `test_server_name_without_port_uses_the_default_port` | Client connection error handling: a server name without a port connects to `DEFAULT_PORT`, instead of failing to split. | `DEFAULT_PORT` is patched to the stand-in's port, so no fixed port is used. |
| `test_malformed_server_name_raises_value_error` | Client connection error handling: a server name with an empty or non-numeric port, or an empty host, raises `ValueError`, and the client stays disconnected. | Parametrized over `127.0.0.1:`, `127.0.0.1:abc` and `:7111`. |

### TestDisconnect

| Test | Purpose | Approach |
|---|---|---|
| `test_disconnect_waits_for_the_manager_without_sleeping` | Client Low (the disconnect sleep): `disconnect()` doesn't sleep a fixed 100 ms, and the manager still removes the module. | `time.sleep` in `pyrtma.client` is replaced by a recorder during `disconnect()`; then waits for the module to leave the manager's table. |
| `test_disconnect_is_bounded_when_the_manager_keeps_the_socket_open` | Client Low (the disconnect sleep): when the manager doesn't close its end, `disconnect()` gives up after its short wait. | `scripted_client`, whose stand-in never closes the connection; the call must take less than `SLACK`. |

### TestClientContext

| Test | Purpose | Approach |
|---|---|---|
| `test_client_context_passes_auto_detect` | H8: `client_context(auto_detect=False)` gives a client with the core definitions only, though compiled test definitions are loaded. | Looks up the name of `TEST_START`, which only the test definitions have. |
| `test_client_context_disconnects_when_the_body_raises` | H8: when the body raises, the client is disconnected and the manager removes it. | A body that raises `RuntimeError`; then checks `connected` and the manager's table. |

### TestDefinitions

These tests use `isolated_modules`, which takes every loaded definitions module out of `sys.modules` and clears `PYRTMA_MSGDEF_MODULES` for the test, and `definitions_module()`, which adds a stand-in compiled module whose `get_message_definitions()` returns the definitions given. Nothing connects.

| Test | Purpose | Approach |
|---|---|---|
| `test_two_definitions_modules_raise` | H7: with two definitions modules loaded, auto-detection raises `MessageDefinitionsLoadError` naming both, in every run, instead of picking one by set order. | Two stand-ins, one with the test definitions and one with the core definitions. |
| `test_star_import_of_definitions_is_not_ambiguous` | H7: a module that star-imports a definitions module shares its `get_message_definitions`, and doesn't count as a second one. | A stand-in, and a script module given the same function and version. |
| `test_single_definitions_module_is_used` | H7: one loaded definitions module is used. | One stand-in; compares the client's definitions by identity. |
| `test_no_definitions_module_uses_core_defs` | H7: with no definitions module loaded, the client uses the core definitions. | Looks up `TEST_START` and `ACKNOWLEDGE`. |
| `test_env_var_chooses_among_loaded_modules` | H7: `PYRTMA_MSGDEF_MODULES` picks the first listed module that is loaded and has definitions, without auto-detection, so two loaded modules don't raise. | Two stand-ins; the variable lists a missing module, then the second stand-in. |
| `test_env_var_does_not_import_modules` | H7: `PYRTMA_MSGDEF_MODULES` only looks in `sys.modules` and never imports, as designed. | Names the compiled test definitions, which are importable but taken out of `sys.modules`; they must stay out, and the client falls back to the core definitions. |

### TestSubscriptions

| Test | Purpose | Approach |
|---|---|---|
| `test_generator_subscribes_every_type` | H5: `subscribe()` with a generator subscribes every type it yields. | A generator of three types. |
| `test_generator_removes_every_type` | H5: `unsubscribe()` and `pause_subscription()` with a generator remove every type it yields. | Parametrized over both; three types subscribed, a generator of two. |
| `test_generator_resumes_every_type` | H5: `resume_subscription()` with a generator resumes every type it yields. | Two types subscribed and paused, then resumed from a generator. |
| `test_subscription_context_keeps_existing_subscriptions` | H3: `subscription_context()` leaves types that were already subscribed alone, with a warning, and unsubscribes only the ones it added. | Types A to C subscribed; the context names A to D, the case that used to unsubscribe B. |
| `test_subscription_context_restores_after_exception` | H3: `subscription_context()` unsubscribes what it added when the body raises. | A subscribed; the context adds B and the body raises `RuntimeError`, which must propagate. |
| `test_subscription_context_for_all_types_restores_previous_ones` | H3: on leaving a `subscription_context()` for `ALL_MESSAGE_TYPES`, the individual subscriptions it replaced and the paused types are restored. | A subscribed and B paused before the context. |
| `test_paused_subscription_context_restores_after_exception` | H3: `paused_subscription_context()` resumes what it paused when the body raises. | A and B subscribed; the context pauses A and the body raises. |
| `test_paused_subscription_context_ignores_every_unsubscribed_type` | H3: `paused_subscription_context()` ignores, with a warning, every type that isn't subscribed, so none is subscribed on exit. | A subscribed; the context names B, D and A. Removing B while iterating used to skip D, which was then subscribed on exit. |
| `test_contexts_leave_changes_the_body_made` | H3: on exit, a context reverts only types still in the state it left them, so the body's own changes to them stand. | The body of a `subscription_context([B])` unsubscribes B and subscribes E; the body of a `paused_subscription_context([A])` resumes and then unsubscribes A. |
| `test_context_exit_after_disconnect_does_not_raise` | H3: leaving a context after the client has disconnected restores nothing and raises nothing, so it can't hide an exception from the body. | Parametrized over both contexts; the body calls `disconnect()`. |
| `test_pause_and_resume_of_all_types_round_trips` | Client: pausing `ALL_MESSAGE_TYPES` while subscribed to it leaves it paused, and `resume_all_subscriptions()` subscribes to it again, at the manager too. | Subscribes to `ALL_MESSAGE_TYPES`, pauses it, and checks the manager has nothing before resuming. |
| `test_pausing_all_types_pauses_individual_subscriptions` | Client: pausing `ALL_MESSAGE_TYPES` while subscribed to individual types pauses each of them, matching the manager, which drops them all, and `resume_all_subscriptions()` restores them. | A and B subscribed, then `pause_subscription([ALL_MESSAGE_TYPES])`. |
| `test_unsubscribe_from_all_forgets_paused_types` | Client: `unsubscribe_from_all()` also forgets paused types, so `resume_all_subscriptions()` afterwards subscribes nothing. | A and B subscribed and A paused. |

## test_client_logging.py — `RTMALogger`, `RTMALogHandler` and `RichLogFormatter` (needs: integration for `TestRtmaSending`)

Clients from `quiet_client()` are unconnected and have their console turned off, so tests don't print. `TestRtmaSending` uses `deliver_log()`, which logs a line from a connected sender until a receiver subscribed to `RTMA_LOG_INFO` reads it, because a subscription can race messages from other clients. It matches by type ID and the sender's log name, since the receiver decodes with the compiled test definitions rather than `core_defs`.

### TestLoggerLifecycle

| Test | Purpose | Approach |
|---|---|---|
| `test_live_clients_have_distinct_loggers` | C8: two clients alive at once have different loggers with different names. | Two clients; compares their `logging.Logger` objects and names. |
| `test_new_client_logger_has_only_its_own_handlers` | C8: a new client's logger holds only its own RTMA and console handlers, never those of a garbage-collected client. | Creates and discards 20 clients in turn, so a new one is often allocated at a freed one's address, and compares each logger's handlers with its own two. |
| `test_discarded_clients_release_their_handlers` | C8: discarding clients leaves the total number of handlers across all loggers unchanged. | Counts handlers on every registered logger and the root, creates and discards 50 clients, collects garbage, and counts again. |
| `test_logger_does_not_keep_client_alive` | C8: the finalizer that releases the handlers doesn't keep the client alive. | A weak reference to a client is dead after the client is deleted and garbage collected. |
| `test_close_removes_handlers_and_is_idempotent` | C8: `RTMALogger.close()` removes every handler and turns the outputs off, and can be called twice. | Calls `close()` twice on a client's logger. |
| `test_console_can_be_enabled_again` | Strings, validation and logging: setting `enable_console` back to `True` adds the console handler again. | Turns the console off, then on, and looks for the handler on the logger. |

### TestLogMessageFields

| Test | Purpose | Approach |
|---|---|---|
| `test_non_ascii_text_is_replaced` | Strings, validation and logging: characters that aren't ASCII become `?`, one for one, in the message, path, function name and log name. | `gen_log_msg()` on a record with "kΩ", "µV", a path under "Jürgen", and an accented function and log name. |
| `test_long_message_is_truncated_with_marker` | Strings, validation and logging: a long message that isn't ASCII is replaced, then cut to the field with the `[TRUNCATED]` marker. | A message of 2000 "é" characters. |
| `test_long_fields_are_truncated` | Strings, validation and logging: a path that is too long keeps its end after `...`, and a function name or log name that is too long is cut to its field. | A 600-character path, a 300-character function name and a 200-character log name. |

### TestRtmaSending

| Test | Purpose | Approach |
|---|---|---|
| `test_non_ascii_message_is_sent_and_rtma_stays_enabled` | Strings, validation and logging: logging "kΩ" sends an RTMA log message with "k?" and leaves RTMA logging on. | A sender and a subscribed receiver from `client_factory`, with `deliver_log()`. |
| `test_rtma_logging_resumes_after_reconnect` | Strings, validation and logging: a send that fails when the manager goes away doesn't turn RTMA logging off, and log messages arrive again after the client reconnects. | Connects the sender to a second `ManagerHarness`, stops it, and logs until the client sees the connection is lost; then reconnects to the `manager` fixture and uses `deliver_log()`. |
| `test_disabled_rtma_logging_stays_disabled_after_reconnect` | Strings, validation and logging: RTMA logging that the user turned off stays off across a reconnect. | Turns it off on a connected client, reconnects, and checks the handler isn't attached. |

### TestRichLogFormatter

| Test | Purpose | Approach |
|---|---|---|
| `test_record_is_left_unchanged` | Strings, validation and logging: formatting doesn't alter the record's `msg`. | Formats a record whose message has brackets, then checks `msg`. |
| `test_markup_in_message_and_arguments_is_escaped` | Strings, validation and logging: markup is escaped in the message and in its `%`-arguments. | A `%s` message with markup in both, formatted with `{message}`. |
| `test_message_that_is_not_a_string_is_formatted` | Strings, validation and logging: a message that isn't a string is formatted rather than raising. | A record whose `msg` is 42. |
| `test_file_handler_after_console_sees_original_text` | Strings, validation and logging: a file handler added after the console handler writes the message as logged, without escapes. | A client with the console on and a file handler in `tmp_path`; logs "a [b] c" and reads the file. |

## test_unified_console_log.py — the unified console log (needs: integration for `TestConnect` and the `TestBackoff` tests that open sockets)

Unified logs have their own console output turned off by `quiet()`. `stopping_sleep()` is a stand-in for the wait between connection attempts: it records each delay, returns at once, and calls `stop()` on a given call, so the loop ends without waiting in real time. `run_in_thread()` runs `start()` in a daemon thread when the test has to act while it runs.

| Test | Purpose | Approach |
|---|---|---|
| `test_log_level_names_resolve` | C4: every `--log-level` choice resolves to its level number without `logging.getLevelNamesMapping()`, which Python 3.10 lacks. | Parametrized over the five choices, through `parse_args()`. |
| `test_server_address_comes_from_options` | C4: the manager address is built from `-a` and `-p`, with the defaults when they're absent. | `parse_args()` with no options, then with both. |

### TestConnect

| Test | Purpose | Approach |
|---|---|---|
| `test_init_rtma_connects_to_manager` | C4: `init_rtma()` connects with the current `Client.connect()` signature and subscribes to the log messages. | Against the `manager` fixture; checks the connection and that `RTMA_LOG_INFO` is subscribed. |
| `test_exit_message_stops_the_loop` | C4: `start()` runs against a manager and returns, disconnected, when it receives `EXIT`. | `start()` in a thread; a client from `client_factory` sends `EXIT` until the thread ends, since the subscription can race it. |

### TestBackoff

| Test | Purpose | Approach |
|---|---|---|
| `test_retries_back_off_without_manager` | C4: with no manager listening, each failed attempt waits twice as long as the last, from 0.5 s up to 5 s, instead of retrying at once. | A free port with nothing on it and `stopping_sleep()`, stopping on the sixth wait. |
| `test_delay_resets_after_a_connection` | C4: the wait starts again from 0.5 s after a successful connection. | `init_rtma` is replaced by one that fails twice, then succeeds; the read loop then raises `NotConnectedError`, which counts as a failure. |
| `test_lost_connection_is_retried_with_back_off` | C4: losing the manager mid-run is retried with the same back-off, starting from 0.5 s. | `start()` in a thread against a separate `ManagerHarness`, which is then stopped; the second wait stops the loop. |
| `test_stop_interrupts_the_default_sleep` | C4: `stop()` ends the default wait between attempts at once, rather than after the delay. | A 30-second `retry_delay` and no manager; calls `stop()` after the first attempt and expects the thread to end within 5 s. |

## test_web_manager.py — the websocket bridge (needs: integration for `TestProxyRead` and `TestConnect`)

`StubHandler` is an `RTMAWebSocketHandler` with no websocket behind it. `socketserver` handlers do all their work in their constructor, so it skips the base constructors, sets only the proxy and `keep_alive`, reports the websocket as always ready, and collects what would be sent to it in `sent`.

| Test | Purpose | Approach |
|---|---|---|
| `test_import_keeps_root_handlers` | Web manager: importing `pyrtma.web_manager` leaves the root logger's handlers alone. | A fresh interpreter adds its own root handler, imports the module, and prints whether the handlers are unchanged. |
| `test_configure_logging_replaces_root_handlers` | Web manager: the logging setup works with no handlers at all, and replaces existing ones with one `RichHandler`. | Two stand-alone loggers, one empty and one with a `StreamHandler`. |
| `test_defs_option_is_required` | Web manager: leaving out `--defs` is a usage error. | `parse_args()` without it; expects exit status 2 and `--defs` in the message. |
| `test_definitions_are_loaded_once` | Web manager: `run()` loads the definitions file once, and doesn't import it by name or add its folder to `sys.path`. | A copy of the compiled test definitions in `tmp_path`; `load_message_definitions` is wrapped to count calls, and `run_forever` is replaced so the server closes at once. |

### TestProxyRead

| Test | Purpose | Approach |
|---|---|---|
| `test_unsubscribed_message_does_not_block` | Web manager: reading a message the proxy isn't subscribed to returns without waiting for another. | The real manager follows such a message with an ACK, so a listening socket stands in for it: the proxy connects to it, the peer sends one `TEST_START` and nothing more, and `read_proxy_message()` runs in a thread that must finish within 5 s. |
| `test_partial_message_does_not_block` | C1 (client side): with half a message received, `read_proxy_message()` returns without waiting for the rest, so websocket input isn't held up. | The same listening socket; the peer sends half a `TEST_START` and nothing more, and `read_proxy_message()` must finish within 5 s. |

### TestConnect

The `handler` fixture gives a `StubHandler` whose proxy already has a socket to the `manager` fixture, as `handle()` sets up before the web client's first message. `hello_observer` is a client subscribed to `HELLO`, with its subscription confirmed by `deliver()`, and returns a function that reads until a `HELLO` passes a check.

| Test | Purpose | Approach |
|---|---|---|
| `test_handle_connect_returns_ack` | C4: a web client's `CONNECT` connects the proxy with a dynamic ID and passes the manager's ACK, addressed to that ID, to the websocket. | `handle_connect()` with a `CONNECT`. |
| `test_handle_connect_v2_returns_ack_and_sets_name` | C4: a web client's `CONNECT_V2` connects the proxy under the client's name, which the manager announces in its `HELLO`. | `handle_connect_v2()` with a `CONNECT_V2` named "web-page". |
| `test_connect_json_from_web_client` | C4: a `CONNECT` arriving as JSON, as rtma-js sends it, is answered with an ACK. | `process_json_message()` with the JSON of a `CONNECT`. |
| `test_requested_static_id_gets_dynamic_id` | C4: a web client's request for a static module ID is ignored, and the proxy takes a dynamic one. | Parametrized over `CONNECT`, which asks through its header, and `CONNECT_V2`, which asks in its data; both ask for 50. |
| `test_connect_v2_after_connect_updates_name` | Manager connect messages: a `CONNECT_V2` after the web client's `CONNECT` updates the proxy's name, which the manager announces with a new `HELLO`, without a second ACK to the web client and without a change of module ID. | `handle_connect()`, then `handle_connect_v2()` named "late-page". A wait for an ACK would time out and send an error to the websocket. |
| `test_connect_after_connect_v2_is_ignored` | Manager connect messages: a `CONNECT` after the web client's `CONNECT_V2` changes nothing and sends nothing. | `handle_connect_v2()` named "page", then `handle_connect()`. |

## test_dataset.py — the `Dataset` helper, without a manager (needs: none)

Each `Dataset` is given a stand-in client that keeps what it would send.

| Test | Purpose | Approach |
|---|---|---|
| `test_max_size_mb_is_sent_when_added` | `max_size_mb` is sent in `DATASET_ADD`. | `max_size_mb=20`, then `add()`. |
| `test_default_max_size_is_500_mb` | The default `max_size_mb` is `DATASET_MAX_SIZE_MB`, 500. | A dataset with the defaults. |
| `test_max_size_mb_outside_its_range_raises` | `max_size_mb` outside 1 to 500 raises `ValueError`, and the half-built dataset cleans up without an error of its own. | Parametrized over 0, -1 and 501. |
| `test_subdivide_interval_is_deprecated_and_ignored` | A nonzero `subdivide_interval` warns and isn't sent; the default size is. | `subdivide_interval=30`. |
| `test_positional_subdivide_interval_still_accepted` | `subdivide_interval` is still accepted in its old position, so existing calls run. | Passes it as the fifth positional argument. |

### TestProcessMsg

Messages are passed straight to `process_msg()`, as `poll()` does with what it reads.

| Test | Purpose | Approach |
|---|---|---|
| `test_error_for_this_dataset_is_returned` | C7: a `DATA_LOGGER_ERROR` naming this dataset is returned, rather than raising `AttributeError` on a `name` field the message doesn't have. | An error for `ds`. |
| `test_error_for_another_dataset_is_ignored` | C7: an error naming another dataset is ignored. | An error for `other`. |
| `test_error_for_no_dataset_is_returned` | C7: an error with no dataset name, which is about the data logger as a whole, is returned to every dataset. | An error with an empty `dataset_name`. |
| `test_config_is_stored` | C7: a `DATA_LOGGER_CONFIG` is stored in `datalogger_config`, rather than raising `AttributeError` on a method that doesn't exist, and `process_msg()` returns None. | A config listing one dataset. |
| `test_config_is_none_until_received` | `datalogger_config` is None until a config arrives. | A new dataset. |
| `test_status_for_this_dataset_is_kept` | A status for this dataset is still kept. | A status with `is_recording` set. |

## test_cli.py — the data logger control CLI (needs: none; `TestMain`: integration)

`answer()` replaces `rich.prompt.Prompt.ask` with one that returns scripted answers in turn and records each prompt, returning the prompt's default for an empty answer as rich does. `add_dataset()` is given the `RecordingClient` from `test_dataset.py`, so nothing is sent.

### TestAddDataset

| Test | Purpose | Approach |
|---|---|---|
| `test_uses_the_cli_client` | Data logger: `add_dataset()` sends through the client it is given, the CLI's own, rather than a `Dataset` client of its own on the default server that is never read. | Checks the `DATASET_ADD` the recording client received. |
| `test_bad_message_types_are_asked_again` | Data logger: message types that record nothing or aren't IDs, such as spaces only, `0`, text or a negative number, are reported and asked again, rather than creating a dataset that records nothing or crashing. | Parametrized; the second answer, `1001, 1002`, also shows commas are accepted. |
| `test_too_many_message_types_are_asked_again` | More message types than the 64 a dataset holds are asked again. | 65 IDs, then one. |
| `test_bad_name_is_asked_again` | Data logger: a name too long for its field or not ASCII is asked again, rather than raising when the message is built. | Parametrized over 32 characters and `é`. |
| `test_max_size_mb_is_asked_until_in_range` | `max_size_mb` is asked for, defaults to 500, and is asked again until it is a number from 1 to 500. | Parametrized over the default, a valid value, and invalid values before one. |

### TestMain

| Test | Purpose | Approach |
|---|---|---|
| `test_add_uses_the_given_server` | Data logger: `add` uses the CLI's client, connected to the server given on the command line. | Replaces `add_dataset` with a stand-in that records its client, against the `manager` fixture. |
| `test_bad_argument_is_reported_not_raised` | Data logger: a command whose dataset name is too long or isn't ASCII is reported, and the CLI carries on. | Parametrized over `remove` with 40 characters and `start é`, then `q`. |
| `test_exits_cleanly_without_manager` | With no manager running, the CLI prints one line and exits with status 1, rather than a traceback. | A free port. |

## test_data_logger.py — `DataLogger` with a real manager, and its entry point (needs: integration)

The `data_logger` fixture runs a `DataLogger` in a thread against the `manager` fixture, with the test definitions and a `FakeClock` for its datasets, and stops it with `stop()` at teardown; if `run()` raises, the `thread_exceptions` fixture fails the test. The `controller` fixture is a client subscribed to `Dataset.DATALOGGER_TYPES` that sends the requests. `wait_for_logger()` sends `DATA_LOGGER_CONFIG_REQUEST` until a `DATA_LOGGER_CONFIG` comes back, which shows the logger's and the client's subscriptions are in place; because the logger answers requests in order, the same exchange also serves as a barrier after other requests. Datasets record with the `json` formatter into `tmp_path`. `StaleTestStart` is `TEST_START` with 8 bytes instead of 4, as an out-of-date definition would send it, and `UnknownMessage` is type 7777, which the logger's definitions don't have. `events()` lists the dataset events (`DATA_LOGGER_ERROR`, `STARTED`, `STOPPED`, `SAVED`, `REMOVED`) about one dataset, in the order they arrived.

| Test | Purpose | Approach |
|---|---|---|
| `test_main_exits_cleanly_without_manager` | Low: `python -m pyrtma.data_logger` with no manager running exits with status 1 and a one-line error, rather than a traceback. | Calls `main()` with `-m` set to a free port and `-d` the test definitions, and checks `SystemExit` and stderr. |

### TestUndecodableMessages

| Test | Purpose | Approach |
|---|---|---|
| `test_stops_only_datasets_that_record_it` | C5: a message the logger's definitions can't decode doesn't stop the logger. A dataset that records it is stopped and reported, in order, with `DATA_LOGGER_ERROR` naming the type and error, `DATASET_STOPPED`, `DATASET_SAVED` and `DATASET_REMOVED`, and its file is kept. A dataset that doesn't record that type keeps recording. | Parametrized over a stale `TEST_START` and an unknown type; one dataset records everything, one only `TEST_END`, which is sent afterwards and must be in its file. |
| `test_unrecorded_type_is_warned_about_once` | C5: messages that can't be decoded and that no dataset records are warned about once per type and error, not once each, and recording carries on. | Three stale `TEST_START`s with only a `TEST_END` dataset recording; counts the warnings with `caplog` and asks for the dataset's status. |

### TestDatasetFailures

| Test | Purpose | Approach |
|---|---|---|
| `test_writer_failure_is_reported_while_others_record` | C5: a dataset whose writer fails is reported with `DATA_LOGGER_ERROR` naming the error, then `DATASET_STOPPED` and `DATASET_REMOVED`, while another dataset keeps recording. | A formatter that fails as on a full disk, registered for the test, and a `json` dataset; the clock is advanced past a write period. |
| `test_failing_request_handler_is_reported` | C5: a request whose handling raises something other than a `DataLoggerError` is reported with `DATA_LOGGER_ERROR` naming the exception, and the logger keeps answering. | Replaces the logger's `send_config` with one that raises `RuntimeError`, then adds a dataset. |

### TestRequests

| Test | Purpose | Approach |
|---|---|---|
| `test_start_all_twice_is_harmless` | C5: a second `DATASET_START "all"` skips the dataset that is already recording, without an error, and it keeps recording. | Starts all twice, then a config barrier and a status request. |
| `test_directed_request_is_answered_to_its_sender` | C6: a request addressed to the logger is answered to its sender only, and a broadcast request is still answered with a broadcast that other modules see. | An observer subscribed to the replies; a directed `DATASET_ADD`, then a broadcast one as a marker, which the observer must receive without the first. |
| `test_request_addressed_to_another_module_is_ignored` | Data logger requests: a request addressed to another module, which the manager copies to logger modules, isn't acted on. | A `DATASET_ADD` addressed to another client, then a config request, which must list no datasets. |
| `test_max_size_mb_from_the_request` | A request's `max_size_mb` from 1 to 500 is used as given. One outside that range, such as the 0 or interval that a client built before `max_size_mb` replaced `subdivide_interval` sends, is replaced by 500 with a warning, so that client keeps recording. | Parametrized over 20, 0, -5 and 900; reads the limit back from `DATA_LOGGER_CONFIG`. |
| `test_full_logger_refuses_before_creating_folders` | Data logger: with `MAX_DATASETS` datasets configured, another is refused with `DataLoggerFullError` before its save folder is created. | Adds six datasets, then a seventh with a new folder. |
| `test_duplicate_name_refused_before_creating_folders` | Data logger: a second dataset with a name in use is refused with `DatasetExistsError` before its save folder is created. | Two datasets named `same`, in different folders. |
| `test_duplicate_file_is_refused_when_added` | Data logger: a dataset that would write to another dataset's file is refused when it is added, with an error naming that dataset. | Two datasets with the same folder, file name and formatter. |

### TestRemoval

| Test | Purpose | Approach |
|---|---|---|
| `test_reset_reports_saved_files` | Data logger requests: `DATA_LOGGER_RESET` reports each recording dataset's saved file before removing it, rather than removing it before the writer finishes. | Resets while one dataset records. |
| `test_remove_after_stop_reports_saved_file_once` | Data logger requests: `DATASET_REMOVE` right after `DATASET_STOP` waits for the file, so `DATASET_SAVED` comes before `DATASET_REMOVED`, and each is sent once. | Sends both requests back to back, then a config barrier to collect anything late. |
| `test_exit_reports_stopped_and_saved` | Data logger requests: when the logger stops, a recording dataset's `DATASET_STOPPED` and `DATASET_SAVED` are sent before it disconnects, and the file is finished. | Calls `stop()` while a dataset records. |

## test_dataset_writer.py — `DatasetWriter`: write failures, slow writes, pause and resume, and its files (needs: none)

Each writer saves to `tmp_path` with a stand-in formatter registered as `stub` for the test. It writes a header line, one line per message (the message's `name` field) and a footer line, and flushes after each write. Its writes can be held at a gate, which shows when a write has begun, or made to raise; so can its constructor. Writers take a `FakeClock` from `helpers.py`, which moves only when the test advances it, so write periods and subdivisions need no waiting. `write_now()` advances past a write period and calls `update()`. The `make_writer` fixture stops every writer and joins its thread at teardown.

| Test | Purpose | Approach |
|---|---|---|
| `test_formatter_that_takes_nothing_fails_the_dataset` | C9: a formatter that takes no messages even into a new file fails the dataset with `DatasetWriterError`, instead of making new files forever. | A formatter whose `write()` always returns 0. |

### TestWriterFailure

| Test | Purpose | Approach |
|---|---|---|
| `test_write_error_stops_recording_and_reports_it` | C5: an `OSError` from the formatter, such as a full disk, doesn't escape the write thread. The dataset stops recording and is marked failed, the error names the dataset, the exception type, the message and the file, later messages aren't buffered, and the formatter's `discard()` is called. | The stand-in raises `OSError(ENOSPC)` on write; the autouse `thread_exceptions` fixture fails the test if anything escapes the thread. |
| `test_dataset_error_in_writer_stops_recording` | C5: a `DataLoggerError` in the write thread, here a rollover whose next file already exists, stops recording instead of leaving the dataset dead but recording. The finished first file is kept and reported, and the file in the way is untouched. | Creates `rec_0001.txt` first, then writes more than one file holds. |
| `test_error_text_fits_its_fields` | Data logger writer: an error whose text isn't ASCII or is too long for `DATA_LOGGER_ERROR`'s fields is still recorded, with the other characters replaced by `?` and the text cut with a marker. | A long French `OSError` message, like a localized Windows one, and a 31-character dataset name. |

### TestSlowWrites

| Test | Purpose | Approach |
|---|---|---|
| `test_slow_write_keeps_buffering` | C5: a write that hasn't finished when the next is due doesn't raise. Messages keep being buffered and are all written, in order, once the writer is free. | Holds the gate during the first write, makes a second write due, then opens it. |
| `test_falling_behind_warns_once_and_reports_catching_up` | C5: a writer that falls behind logs one warning however many writes fall due meanwhile, and one message when it catches up. | Three writes fall due while the gate is closed; counts the writer logger's records with `caplog`. |
| `test_stop_while_behind_writes_everything` | C5: stopping a dataset whose writer is behind still writes every buffered message and finalizes the file. | Stops while the gate is closed with a second write due, then opens it. |

### TestPauseResume

| Test | Purpose | Approach |
|---|---|---|
| `test_resume_when_not_paused_keeps_elapsed_time` | Data logger: `resume()` on a dataset that isn't paused, as `resume "all"` does, changes nothing and returns False; its elapsed time and write schedule carry on. | Resumes after 10 s and checks the elapsed time, then that a write still falls due one write period after the start. |
| `test_pause_before_start_does_nothing` | Data logger: `pause()` and `resume()` on a dataset that isn't recording change nothing and return False. | A dataset that was never started. |
| `test_pause_and_resume_track_elapsed_time` | Elapsed time stops while a dataset is paused and carries on after it resumes. | Pauses at 5 s for 100 s, then resumes for 2 s. |

### TestStartAndFiles

| Test | Purpose | Approach |
|---|---|---|
| `test_start_twice_raises_dataset_in_progress` | C5: starting a dataset a second time raises `DatasetInProgress`, which the logger reports, rather than `RuntimeError` from starting its thread again, and it keeps recording. | Calls `start()` twice. |
| `test_second_writer_for_same_file_is_refused` | Data logger: of two datasets with the same path and file name, which both pass the check when added, the second to start raises `DatasetExistsError` and starts nothing, and the first one's file isn't truncated. | The first writes a message before the second starts. |
| `test_failed_start_leaves_no_thread_and_no_file` | Data logger: when the file can't be started, `start()` raises `DatasetError` with the cause, leaves no write thread running, isn't recording, and removes the file it created. | The stand-in's constructor raises `OSError(EACCES)`, after the writer is constructed. |
| `test_save_path_that_cannot_be_created_raises_dataset_error` | C5: a save path that can't be created for a reason other than a missing parent or permissions raises `DatasetError`, which the logger reports, not a raw `OSError`. | A save path inside a regular file. |
| `test_stop_writes_buffered_messages_and_saves` | Stopping writes the buffered messages, finalizes the file, and records it as saved. | Two messages, then `stop()`. |
| `test_default_clock_ignores_wall_clock_steps` | Data logger writer: by default the write schedule uses a monotonic clock, so a step of the wall clock doesn't make a write due. | Replaces `time.time` with one an hour ahead after the dataset starts. |

### TestRollover

The stand-in's limit is set, through its class's `max_bytes`, with room for its header, two one-letter lines and its footer, counting newlines as the platform writes them.

| Test | Purpose | Approach |
|---|---|---|
| `test_full_file_continues_in_a_new_one` | C9: when a file is full, the dataset continues in `rec_0001`, `rec_0002` and so on, each within the limit, with every message in order across them and each file saved. | Three messages in one write, then two at stop. |
| `test_subdivide_interval_is_ignored` | `subdivide_interval` is deprecated: a nonzero value warns and no longer splits files by time. | An interval of 30 s, ten minutes of recording, one file. |
| `test_max_size_mb_sets_the_file_limit` | A dataset's `max_size_mb` becomes its formatter's `max_bytes`, in MB of 1,000,000 bytes. | `max_size_mb=20`. |
| `test_formatter_limit_below_max_size_mb_wins` | A formatter whose own `max_bytes` is lower than the dataset's limit keeps it. | A formatter limit of 1000 bytes and `max_size_mb=20`. |
| `test_max_size_mb_outside_its_range_is_refused` | `max_size_mb` outside 1 to `DATASET_MAX_SIZE_MB` raises `DatasetError` before anything is created. | Parametrized over 0, -1 and 501. |
| `test_default_max_size_is_500_mb` | The default `max_size_mb` is `DATASET_MAX_SIZE_MB`, 500. | A writer with the defaults. |
| `test_rolled_over_quicklogger_files_all_read` | C9: QuickLogger files from a rollover are each within the limit and together read back every message, in order. | The real `quicklogger` formatter with room for three messages, and seven messages. |
| `test_crash_keeps_finished_files_readable` | C9: if the logger dies while recording, the files it finished read completely, and the one it was writing loads nothing with `throw=False` rather than raising. | Reads both files after a rollover, while the second is still open. |
| `test_formatter_without_a_count_is_not_split` | A formatter written before `write()` returned a count, whose `write()` returns None, still writes everything to one file. | A formatter overriding `write()` the old way, with a small limit. |

## test_data_formatter.py — formatter registration and the file size limit (needs: none)

`starts()` from `tests/ql_files.py` supplies `TEST_START` messages with increasing IDs.

| Test | Purpose | Approach |
|---|---|---|
| `test_duplicate_formatter_name_error_has_its_message` | Data logger writer: registering a formatter name twice raises `DataFormatterKeyError` with its text in `msg` and no dataset, rather than the text as the dataset name and an empty message. | Registers one class twice into an emptied registry. |
| `test_default_limit_is_500_mb` | Every formatter's default limit is 500,000,000 bytes. | Reads `DataFormatter.max_bytes`. |
| `test_write_leaves_room_for_the_footer` | `write()` takes only the messages that leave room for the footer within `max_bytes`, and returns how many it took. | A text formatter with a 7-character header and footer, and a limit that fits three one-digit lines. Sizes count each newline as the platform's line ending. |
| `test_first_message_is_written_even_past_the_limit` | An empty file always takes one message. | A limit of 1 byte. |
| `test_limit_counts_encoded_bytes` | The limit counts UTF-8 bytes on disk, not characters. | Lines of `é`, two bytes each, and a limit that fits exactly two. |

## test_quicklogger.py — the QuickLogger formatter (needs: none)

`tests/ql_files.py` builds QuickLogger version 1 files by hand from the layout the existing readers use, MATLAB's included: a file header of six 32-bit fields, every message header, a 32-bit offset per message, then the data, in native byte order. It doesn't use the formatter, so comparing against it checks that the format is unchanged. The messages are `TEST_START`s with increasing IDs and receive times.

| Test | Purpose | Approach |
|---|---|---|
| `test_single_batch_matches_the_v1_layout` | QuickLogger formatter: the formatter can be constructed, and a recording finalized in one batch is byte for byte a version 1 file. | Three messages through `finalize()` only, compared with `v1_file()`. |
| `test_several_batches_match_the_v1_layout` | QuickLogger formatter: a recording written in several batches, whose data goes through the temporary file, is byte for byte the same version 1 file. | Seven messages in two writes and a final batch. |
| `test_recording_round_trips_through_log_reader` | QuickLogger formatter: what the formatter writes, `LogReader` reads back. | Five messages in two batches, read with the test definitions. |

### TestSizeLimit

| Test | Purpose | Approach |
|---|---|---|
| `test_write_stops_before_the_limit` | C9: `write()` takes only the messages that keep the finished file within `max_bytes` and returns how many it took, so the file never passes the limit and stays a valid v1 file. | A limit with room for exactly three messages; five offered, then the other two. |
| `test_first_message_is_written_even_past_the_limit` | C9: an empty file always takes one message, so a message larger than the limit can't stall a dataset. | A limit of 1 byte. |
| `test_finalize_writes_every_message_it_is_given` | `finalize()` writes all the messages passed to it, whatever the limit. | A limit of 1 byte and three messages to `finalize()`. |
| `test_default_limit_is_500_mb` | C9: the QuickLogger formatter's default limit is 500,000,000 bytes. | Reads the class attribute. |

### TestSpill

| Test | Purpose | Approach |
|---|---|---|
| `test_small_recording_never_creates_a_spill_file` | C9: data under the spill threshold stays in memory, so a small recording writes only its `.bin`. | Lists the folder after finishing. |
| `test_data_past_the_threshold_spills_beside_the_recording` | C9: data past the threshold moves to `rec.bin.tmp` beside the recording, not the system's temporary folder; the finished file is still byte for byte a v1 file, and the spill file is deleted. | A threshold of 10 bytes; checks for the spill file between writes. |
| `test_discard_removes_the_spill_file` | C9: `discard()`, which the writer calls when writing fails, deletes the spill file. | Spills, then discards. |
| `test_stale_spill_file_from_a_crash_is_replaced` | C9: a spill file left by a crashed logger doesn't stop a new recording of the same name; it is replaced. | Writes junk at the spill path first. |
| `test_offsets_take_four_bytes_each` | C9: offsets are stored in a 4-byte array, not as Python ints. | Checks `offsets.itemsize` and the values. |

## test_log_reader.py — `LogReader` on QuickLogger files (needs: none)

Files are built with `tests/ql_files.py` (see `test_quicklogger.py`), so they have exactly the layout of files written before this change. `StaleTestEnd` is `TEST_END` with 8 bytes instead of 4, as an out-of-date definition would record it, and `UnknownMessage` is type 7777, which the test definitions don't have.

| Test | Purpose | Approach |
|---|---|---|
| `test_reads_a_file_with_the_v1_layout` | A version 1 file, as written before this change, still reads. | Four messages. |
| `test_excluded_type_is_skipped_before_it_is_checked` | Data logger: a type in `exclude` is skipped before it is checked against the definitions, so a stale or unknown type can be excluded to load the rest of the file. | Parametrized over a stale type by number and by name, and an unknown type by number, between `TEST_START`s. |
| `test_included_types_are_chosen_before_others_are_checked` | Data logger: with `include`, other types are skipped before they are checked. | A stale and an unknown message after two `TEST_START`s, with `include=["TEST_START"]`. |
| `test_stale_type_still_raises_when_not_filtered` | A stale message that isn't filtered out still raises `MessageDefinitionsError` naming the type. | One stale `TEST_END`, no filters. |
| `test_truncated_data_loads_as_far_as_it_goes` | Data logger: with `throw=False`, a file whose data block was cut short, as by a crashed logger, loads every message whose data is complete and logs a warning, instead of raising `ValueError`. | Parametrized over a cut inside the last message's data and one that removes the last two messages' data. |
| `test_file_truncated_before_its_data_loads_nothing` | Data logger: with `throw=False`, a file cut before its data block loads no messages and logs a warning, instead of raising. | Parametrized over cuts in the file header, the message headers and the offsets. |
| `test_truncated_file_raises_a_clear_error` | Data logger: with `throw=True`, a truncated file raises a `ValueError` that says the file is truncated. | A file cut inside its last message's data. |
| `test_imports_without_tkinter` | Data logger: the module imports where `tkinter` isn't available, and asking it to show a file dialog then raises `RuntimeError` naming `tkinter`. | Sets `sys.modules["tkinter"]` to None and imports the module again, then calls `LogReader(None)`. |

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

The module-level tests load files written to `tmp_path`, so each test's file has its own module name in `sys.modules`.

| Test | Purpose | Approach |
|---|---|---|
| `test_failed_import_leaves_nothing_in_sys_modules` | Loader and definitions: a definitions file that raises while importing leaves no half-initialized module in `sys.modules`. | A file that raises `RuntimeError`; compares the loader's `_pyrtma_defs_` modules before and after. |
| `test_failed_import_can_be_retried` | Loader and definitions: once the file is fixed, loading it again works, so a failed import isn't cached. | The broken file is replaced by a copy of the compiled test definitions and loaded again. |
| `test_loading_a_file_twice_gives_the_same_classes` | Loader and definitions: loading the same file twice returns the same message classes, instead of executing it again. | A copy of the compiled test definitions, loaded twice; compares the `TEST_START` classes by identity. |
| `test_errors_from_get_message_definitions_are_wrapped` | Loader and definitions: an exception from the file's `get_message_definitions()` is raised as `MessageDefinitionsLoadError`, with the original as its cause. | A file whose `get_message_definitions()` raises `KeyError`. |

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

| Test | Purpose | Approach |
|---|---|---|
| `test_validation_is_enabled_again_after_an_exception` | H6: validation is on again after the body of `disable_message_validation()` raises. | A body that raises `RuntimeError`; then an out-of-range `int8` must raise `ValueError`. |
| `test_generator_assigns_every_value` | H5 (validators): assigning a generator to an array slice validates and stores every value. | Parametrized over `int8`, `uint64`, byte and float arrays. |
| `test_generator_assigns_every_struct` | H5 (validators): the same for a struct array. | A generator of four structs with distinct `int32` values. |
| `test_generator_with_a_value_out_of_range_is_rejected` | H5 (validators): a generator still gets every value checked. | A generator whose last value doesn't fit `int8`. |
| `test_validate_many_reads_a_generator_once` | H5 (validators): `validate_many` accepts a generator of valid values; it used to iterate up to three times and fail on the empty remainder. | Parametrized over integer, byte and float validators. |
| `test_get_field_raw_returns_the_field_bytes` | Client `get_field_raw`: it returns a copy of a field's raw bytes. | An `int32` and a `char[4]` field. |
| `test_get_field_raw_rejects_an_unknown_field` | Client `get_field_raw`: an unknown name raises `KeyError`, as documented. | A name the message doesn't have. |
| `test_from_dict_leaves_its_input_unchanged` | Low (`from_dict`): `from_dict` doesn't modify the dictionary it is given, including nested ones. | Char fields given as lists of characters, at the top level and in a struct; compared with a deep copy. |
| `test_from_dict_keeps_the_cause_of_a_failure` | Low (`from_dict`): a failure raises `JSONDecodingError` with the original exception as its cause. | An empty dictionary, which raises `KeyError` inside. |
| `test_message_copy_keeps_the_header_class` | Low (`Message.copy`): `Message.copy` works, copies the data, and keeps the header's class. | A message with a `MessageHeader` subclass; compares classes, bytes and identity. |
| `test_string_that_is_not_ascii_raises_on_read` | Strings, validation and logging: a string field holding bytes that aren't ASCII raises on read, as decided in Phase 5. | UTF-8 bytes written to the raw field, past the validator. |
| `test_string_that_is_not_ascii_is_rejected_on_write` | Strings, validation and logging: assigning text that isn't ASCII raises `TypeError`. | Assigns "ó". |

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
