# Changelog

Behavior changes to pyrtma are recorded here, under "Unreleased", in the same change
that makes them. The version number is chosen at release time.

## Unreleased

### Changed

- `from_random()` fills int64 and uint64 fields across their whole range on every platform; on Linux they previously stayed within 32 bits. Float and double fields now get finite values with random sign and magnitude, rather than values in [0, 1).
