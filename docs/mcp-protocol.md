# TH-D75 MCP protocol notes

## Entry

Send at 9600 baud:

```text
0M PROGRAM\r
```

The clean response is `0M\r`. **Do not prepend CR** on this firmware: a leading
empty line makes the radio answer `?\r` first, which breaks strict upstream
implementations.

Entry does not change the USB device number.

## Page read

```text
Host: R <page:2 be> 00 00                  (5 bytes)
Radio: W <page:2 be> 00 00 <256 bytes>     (261 bytes)
Host: 06
Radio: 06
```

## Page write

```text
Host: W <page:2 be> 00 00 <256 bytes>      (261 bytes)
Radio: 06
```

Writes are followed by a read-back for verification. Only pages containing
changed fields are written.

## Idle timeout and keepalive

This firmware drops the MCP session after roughly **2 seconds** without
traffic. Immediate repeated page reads are fine; idle is the failure mode.

The persistent settings backend sends one harmless page read every **0.5 s**
while settings mode is active. This prevents the session from going silent
without causing a USB reset.

## Exit

Send `E`. The radio may disconnect USB before its final ACK is readable; then
the device re-enumerates. Exactly one USB reset is expected on exit.

## Failure mode

A wedged MCP session can leave CAT unresponsive until the radio is power-cycled.
The service never opens MCP concurrently with the monitor and restarts
`d75mon` in a `finally` path.

## CHIRP clone fallback

CHIRP's clone protocol uses the same MCP page mechanics but performs a
full-image download/upload and exits MCP multiple times, causing several USB
resets per operation. It is useful as a recovery/backup path but not suitable
for interactive settings editing on this radio.

## CHIRP driver details

- Entry: `0M PROGRAM` **without** a leading CR.
- After entry CHIRP switches to 57600 baud; this implementation stays at 9600
  and is kept alive with the 0.5 s keepalive.
- CHIRP tolerates up to 10 bytes looking for the write ACK.
