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

### Changed

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

### Fixed

- One client could freeze the whole message manager (C1): a client that stopped partway through a message, such as one paused between sending its header and its payload, left the manager blocked reading from it, and every other client's connect timed out. The manager now serves the other clients meanwhile, and drops the stalled client after the stall timeout.
- A slow consumer whose connection had some room, but not enough for a whole message, could block the manager in a send until the consumer read again.
- The message manager no longer crashes on a header with a negative `num_data_bytes`. It drops that client and logs an error naming the size; the oversized case now logs the size too.
- An unexpected exception while handling one client's message is logged with its traceback and drops that client, instead of stopping the manager. A failure while accepting a connection is logged and the connection discarded.
- The message manager no longer crashes when several subscribers or logger modules fail at once, as when a rig is power-cycled. Each is removed once, with one `GOODBYE`, and any `OSError` on a send drops the module, not only `ConnectionError`. Removing a module that was already removed does nothing.
- Subscribers that aren't the destination of a directed message are no longer counted as drops, and no longer cause `FAILED_MESSAGE`, when they aren't writable.
- `FAILED_MESSAGE` reports the original message's `msg_count`, rather than the count of whichever module happened to be sent it before the failure.
- The message manager's `sockets` list no longer grows with every connection; a module's socket leaves it when the module is removed.
