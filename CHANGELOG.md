# Changelog

Behavior changes to pyrtma are recorded here, under "Unreleased", in the same change
that makes them. The version number is chosen at release time.

## Unreleased

### Removed

- The timecode message header (`TimeCodeMessageHeader`) and the `timecode` argument of `Client`, `client_context` and `MessageManager`, with the manager's and the examples' `-t/--timecode` option. Only Python clients could produce that header; the C, MATLAB and JavaScript compilers never did. `get_header_cls()` takes no argument and always returns `MessageHeader`. The standard header is unchanged.
- Positional arguments after `host_id` in `Client` and `client_context`, and after `port` in `MessageManager`. They are keyword-only now, so a call that passed `timecode` positionally raises `TypeError` instead of shifting the arguments after it.

### Added

- `MessageManager(stall_timeout=...)` and the manager's `--stall-timeout SECONDS` and `--no-stall-timeout` options. A client that sends part of a message and then nothing more for this long is dropped, with a warning giving the bytes received. The default is 5 seconds; `None`, or `--no-stall-timeout`, never drops it, for example while it is paused at a debugger breakpoint. A stalled client doesn't hold up other clients either way.
- `MessageManager(logger_timeout=...)` and `--logger-timeout SECONDS`. A logger module that can't take a message for this long is dropped, with an error, a `FAILED_MESSAGE` and a `GOODBYE`. The default, `None`, keeps the current behavior of waiting for loggers as long as it takes.
- The message manager allows at most `MAX_MODULES` (256) connected modules. A `CONNECT` beyond that is refused, with an error, and its connection closed.
- The manager refuses a connection that `select()` couldn't watch, with a warning, instead of stopping: past 512 sockets on Windows, or with a descriptor numbered 1024 or higher on Linux and macOS. A manager whose listening socket would be beyond that limit raises `RuntimeError` when constructed.
- `RTMALogger.close()` removes and closes the logger's handlers. It runs by itself when the logger's client is garbage collected.
- `RTMA_UnifiedLog(retry_delay=..., max_retry_delay=..., sleep=...)`, keyword-only, and `RTMA_UnifiedLog.stop()`, which makes `start()` return from another thread. `pyrtma.unified_console_log` also has `parse_args()` and `main()`; `python -m pyrtma.unified_console_log` runs `main()`.
- `pyrtma.web_manager` has `parse_args()`, `run()` and `configure_logging()`, and `main()` takes an optional argument list.

### Changed

- `Client.send_message`, `send_signal` and `forward_message` return `True` when the message was sent and `False` when the socket wasn't writable within the caller's `timeout` and the message was dropped. They used to return `None` and print `x`; the drop is now logged at debug level on the `pyrtma.client` logger. With the default timeout, which blocks, they always return `True` or raise.
- `Client.unsubscribe_from_all()`, and so `reset_subscriptions()`, also forgets paused subscriptions, so a later `resume_all_subscriptions()` doesn't subscribe to them again.
- `Client.pause_subscription([ALL_MESSAGE_TYPES])` records what it paused: `ALL_MESSAGE_TYPES` itself, or every individually subscribed type, all of which the manager drops. `resume_all_subscriptions()` restores them; it used to resume nothing.
- The subscription context managers revert only types still in the state they left them, so changes the body made to those types stand, and restore nothing once the client has disconnected. A `subscription_context()` for `ALL_MESSAGE_TYPES` restores the individual and paused subscriptions it replaced.
- `Client.read_message` discards messages the client isn't subscribed to without decoding them, so a queued message of an unknown type, or one that doesn't match its definition, no longer raises unless the client is subscribed to it.
- The client's socket is non-blocking once connected; waiting is done in `select()`. Code that reads or writes `Client.sock` directly sees a non-blocking socket. A `select()` on it still shows whether a message is waiting, because the client never reads past the message it is receiving.
- A lost connection closes `Client.sock`, as `disconnect()` does, and clears the client's subscriptions; code that calls `select()` on the socket should check `Client.connected` first. A send that fails with any `OSError` raises `ConnectionLost`, not only a `ConnectionError`.
- The client treats a header announcing a negative payload, or one over 1 MiB, the manager's limit, as a lost connection: it raises `ConnectionLost` naming the size and disconnects, since the stream can't be read further.
- `Client.discard_messages()` returns False only if its timeout ended with a complete message still waiting.
- A received message's `recv_time` is when the whole message had arrived, rather than when its header had.
- A `Client` no longer allocates an unused 1 MiB receive buffer.
- `from_random()` fills int64 and uint64 fields across their whole range on every platform; on Linux they previously stayed within 32 bits. Float and double fields now get finite values with random sign and magnitude, rather than values in [0, 1).
- The message manager forwards each message with the sender's `msg_count` unchanged. Recipients previously saw a per-recipient counter in its place. Messages that originate from the manager, such as ACKs, `HELLO`, `GOODBYE` and `FAILED_MESSAGE`, carry a `msg_count` of 0. `Module.msg_count` still counts the messages sent to each module, but is no longer written into headers.
- The message manager drops a client that sends a core message (type below 100) whose `num_data_bytes` doesn't match its core definition, and logs an error naming the type and both sizes. The message isn't processed or forwarded. Previously the manager acted on whatever bytes were in its buffer.
- A message of an unknown core type is no longer forwarded after its sender is dropped.
- When a send to a module fails during a forward, its `GOODBYE` is sent after the forward finishes, so it follows the module's `FAILED_MESSAGE` instead of preceding it.
- The message manager's client connections are non-blocking. It reads whatever has arrived of each client's message into that client's own buffer, and processes the message once it is complete. `MessageManager.read_message` returns `None` until a message is complete.
- The manager sends each message's header and payload in one buffer, built once and shared by all its recipients, so a recipient gets one send instead of two. The bytes are unchanged.
- When a connection takes only part of a message, the manager keeps the rest and sends it as soon as there is room, before anything else. Messages forwarded to that module meanwhile are counted as drops and reported with `FAILED_MESSAGE`, as for a connection with no room at all; ACKs are queued behind the rest instead of being dropped. A slow consumer is never disconnected for being slow. `Module.send_message` and `Module.send_ack` queue what the connection can't take instead of blocking.
- A client that closes its connection is logged as "Connection closed by the client", or "Connection closed mid-message" with the bytes received, instead of "Wrong number of header bytes". A client dropped for closing or stalling is removed before the warning is logged, so it isn't sent the warning itself.
- `MessageManager.wlist` and `MessageManager.write_timeout` are no longer used. They remain as attributes.
- The message manager sends a `GOODBYE` only for a module that connected, so each `GOODBYE` matches an earlier HELLO. A socket that is closed before it connects, or a module refused at connect, gets none.
- A module refused because its static ID is out of range or already in use no longer takes that ID.
- The reply to `INTRODUCE` has a HELLO for each connected module only. It no longer includes the manager's own entry or sockets that haven't connected, which all appeared with ID 0.
- A socket must send `CONNECT` before anything else. The manager drops a socket that sends any other message first, with a warning, and doesn't act on or forward that message.
- A message whose handling drops its sender, such as a refused `CONNECT`, is no longer forwarded. `DISCONNECT` still is.
- A module can no longer take `DYN_MOD_ID_START` (10000), the first dynamic ID, as a static ID. Static IDs are 1 to 9999.
- `MessageManager.send_to_loggers` takes a keyword-only `exclude`, a logger not to send the message to.
- Each `RTMALogger` has its own `logging` logger, named `pyrtma.logger.<n>` from a counter, instead of one named after `hex(id(client))`. Code that looked a client's logger up by that name should use `client.logger.logger`.
- `RTMALogHandler` no longer turns RTMA logging off when a send fails. A record whose send raises a `ClientError`, such as `ConnectionLost`, is dropped, and sending resumes after the client reconnects. Other errors are reported through `Handler.handleError`. `RTMALogger.enable_rtma` changes only when it is set.
- RTMA log messages replace characters that aren't ASCII with `?`, one for one, in the message, name, path and function name. A path that is too long keeps its end, after `...`; a name or function name that is too long is cut. The wire format and field sizes are unchanged.
- The unified console log waits between connection attempts while the message manager can't be reached. The wait starts at 0.5 seconds, doubles after each failure up to 5 seconds, and starts again from 0.5 seconds after each successful connection. It retries after any `ClientError` or `OSError` from connecting or reading, where it used to retry only after `MessageManagerNotFound` and `ConnectionLost`; failed attempts are logged at debug level.
- Importing `pyrtma.web_manager` no longer changes the root logger. It used to remove the root logger's first handler, whichever that was, and add a `RichHandler`. `main()` now does the setup: it replaces every root handler with a `RichHandler`.
- The web manager's `-d/--defs` option is marked required, so leaving it out gives a usage error with exit status 2 instead of a `TypeError`. Running it with no arguments still prints the help.
- The web manager loads its definitions file once. It no longer also imports the file by its module name or adds its folder to `sys.path`.

### Fixed

- `Client.send_signal` accepts dynamic module IDs, as `send_message` does; it used to reject any ID above 256. Both accept `dest_host_id=ALL_HOSTS`, and so does the message manager, which used to log an error and drop such a message.
- A `Client` whose constructor raises, for example for an out-of-range module ID, no longer raises `AttributeError` from `__del__` when it is collected.
- The `connect()` docstring no longer says that logger modules are subscribed to all message types automatically; they aren't.
- `Client.subscribe`, `unsubscribe`, `pause_subscription` and `resume_subscription` accept any iterable. A generator used to change nothing, because it was empty after a first pass.
- `Client.subscription_context()` and `paused_subscription_context()` restore subscriptions when the body raises. With some lists they also used to skip types while checking them: a context could unsubscribe a type that was subscribed before it, or subscribe on exit a type that never was.
- `Client.read_message(timeout)` honors its timeout as one deadline for the whole call. Each message the client wasn't subscribed to, such as the ACK the manager sends for every subscription change, used to restart the full timeout, so a steady stream of them could block the read indefinitely.
- `Client.read_message` no longer blocks past its timeout when only part of a message has arrived; a timeout of 0 never waits. The bytes received so far are kept, and a later read completes the message. The web manager's proxy no longer holds up websocket input on a partial message either.
- `Client.discard_messages()` and `Client.reset_subscriptions()` empty the queue of messages that have arrived. They stopped after the first message the client wasn't subscribed to, so after `reset_subscriptions()` everything but one message stayed queued.
- `ConnectionLost` always leaves the client disconnected. A reset connection used to leave `Client.connected` true.
- One client could freeze the whole message manager (C1): a client that stopped partway through a message, such as one paused between sending its header and its payload, left the manager blocked reading from it, and every other client's connect timed out. The manager now serves the other clients meanwhile, and drops the stalled client after the stall timeout.
- A slow consumer whose connection had some room, but not enough for a whole message, could block the manager in a send until the consumer read again.
- `INTRODUCE` no longer fails with "dictionary changed size during iteration" when a send fails partway through the reply, which dropped the requesting module and cut the reply short. The module whose send failed is dropped and the rest of the reply goes out.
- A module refused at connect for using another module's static ID no longer causes a `GOODBYE` with that ID while its owner is still connected.
- A logger module is no longer sent its own ACKs twice. The extra copy could be taken as the reply to its next request, before that request was processed.
- The manager's subscription table no longer grows with every message type it forwards, or keeps types whose last subscriber left.
- A connection that `select()` can't watch no longer stops the manager with `ValueError`.
- The message manager no longer crashes on a header with a negative `num_data_bytes`. It drops that client and logs an error naming the size; the oversized case now logs the size too.
- An unexpected exception while handling one client's message is logged with its traceback and drops that client, instead of stopping the manager. A failure while accepting a connection is logged and the connection discarded.
- The message manager no longer crashes when several subscribers or logger modules fail at once, as when a rig is power-cycled. Each is removed once, with one `GOODBYE`, and any `OSError` on a send drops the module, not only `ConnectionError`. Removing a module that was already removed does nothing.
- Subscribers that aren't the destination of a directed message are no longer counted as drops, and no longer cause `FAILED_MESSAGE`, when they aren't writable.
- `FAILED_MESSAGE` reports the original message's `msg_count`, rather than the count of whichever module happened to be sent it before the failure.
- The message manager's `sockets` list no longer grows with every connection; a module's socket leaves it when the module is removed.
- Log lines no longer print several times. A new client could inherit the logger of a client that had been garbage collected, with its handlers, so each line printed once per client ever created at that address; after 200 clients, one logger had 400 handlers.
- Logging text that isn't ASCII, such as "kΩ" or "µV", or from a path longer than 511 characters, no longer switches RTMA logging off for the rest of the process.
- `RichLogFormatter` formats a copy of the record. It used to escape `record.msg` in place, so handlers after the console handler, such as the file handler, logged backslash-escaped brackets. It also escapes markup in the message's arguments, and accepts a message that isn't a string.
- Setting `RTMALogger.enable_console` back to `True` after setting it to `False` adds the console handler again; it used to stay off.
- The unified console log connects again; `connect()` was still passed the removed `allow_multiple` argument and raised `TypeError`. It no longer spins a CPU core and floods its log while the manager is absent, and its `--log-level` option works on Python 3.10, where `logging.getLevelNamesMapping()` doesn't exist.
- The unified console log's remote logger shares the module's own client instead of a throwaway `Client()`, which was garbage collected at once.
- The web manager's handler no longer waits for a further message when the proxy reads one it isn't subscribed to, such as a copy still in flight after the web client unsubscribed. Websocket input was not read while it waited.
- A `CONNECT_V2` from a module that has already connected, such as one that follows its `CONNECT`, updates the module's name and process ID, and the manager announces them with a `HELLO`. It used to be ignored, so a client that sent `CONNECT` first kept no name. No second ACK is sent, because a client that sends both waits for one. A different module ID or logger status in it is logged as a warning and ignored. A `CONNECT` from a connected module is still ignored.
- The web manager connects web clients again (C4). Both `CONNECT` and `CONNECT_V2` from a web client raised `TypeError` or `AttributeError`, because they still passed the removed `daemon_status` and `allow_multiple` arguments, and the handler's thread died. A `CONNECT_V2`'s name becomes the proxy's module name. The proxy still always takes a dynamic module ID; a request for a static one is now logged as a warning. A `CONNECT_V2` after the web client has connected updates the name without a second ACK, and a `CONNECT` after it is ignored, as the message manager does.
