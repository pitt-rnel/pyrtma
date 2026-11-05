# Changelog

Behavior changes to pyrtma are recorded here, under "Unreleased", in the same change
that makes them. The version number is chosen at release time.

## Unreleased

### Removed

- The timecode message header (`TimeCodeMessageHeader`) and the `timecode` argument of `Client`, `client_context` and `MessageManager`, with the manager's and the examples' `-t/--timecode` option. Only Python clients could produce that header; the C, MATLAB and JavaScript compilers never did. `get_header_cls()` takes no argument and always returns `MessageHeader`. The standard header is unchanged.
- Positional arguments after `host_id` in `Client` and `client_context`, and after `port` in `MessageManager`. They are keyword-only now, so a call that passed `timecode` positionally raises `TypeError` instead of shifting the arguments after it.

### Changed

- `from_random()` fills int64 and uint64 fields across their whole range on every platform; on Linux they previously stayed within 32 bits. Float and double fields now get finite values with random sign and magnitude, rather than values in [0, 1).
- The message manager forwards each message with the sender's `msg_count` unchanged. Recipients previously saw a per-recipient counter in its place. Messages that originate from the manager, such as ACKs, `HELLO`, `GOODBYE` and `FAILED_MESSAGE`, carry a `msg_count` of 0. `Module.msg_count` still counts the messages sent to each module, but is no longer written into headers.
- The message manager drops a client that sends a core message (type below 100) whose `num_data_bytes` doesn't match its core definition, and logs an error naming the type and both sizes. The message isn't processed or forwarded. Previously the manager acted on whatever bytes were in its buffer.
- A message of an unknown core type is no longer forwarded after its sender is dropped.
- When a send to a module fails during a forward, its `GOODBYE` is sent after the forward finishes, so it follows the module's `FAILED_MESSAGE` instead of preceding it.

### Fixed

- The message manager no longer crashes on a header with a negative `num_data_bytes`. It drops that client and logs an error naming the size; the oversized case now logs the size too.
- An unexpected exception while handling one client's message is logged with its traceback and drops that client, instead of stopping the manager. A failure while accepting a connection is logged and the connection discarded.
- The message manager no longer crashes when several subscribers or logger modules fail at once, as when a rig is power-cycled. Each is removed once, with one `GOODBYE`, and any `OSError` on a send drops the module, not only `ConnectionError`. Removing a module that was already removed does nothing.
- Subscribers that aren't the destination of a directed message are no longer counted as drops, and no longer cause `FAILED_MESSAGE`, when they aren't writable.
- `FAILED_MESSAGE` reports the original message's `msg_count`, rather than the count of whichever module happened to be sent it before the failure.
- The message manager's `sockets` list no longer grows with every connection; a module's socket leaves it when the module is removed.
