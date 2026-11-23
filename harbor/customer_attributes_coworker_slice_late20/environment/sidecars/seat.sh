#!/bin/bash
# Entry point of every container of the company. At an agent's seat (SEAT and SEAT_TOKEN set) the checkouts under
# /work are pointed at the company's git server, with the seat's holder as the committer. Then the toolchain's own
# entry point runs (it starts the local database).
if [ -n "$SEAT_ONLY" ]; then      # this seat's holder sees its own repository and no other
  for r in /work/*/; do [ "$(basename "$r")" = "$SEAT_ONLY" ] || rm -rf "$r"; done
fi
if [ -n "$SEAT" ]; then
  # A seat holds its holder's repositories, not the company's machinery: the code that runs the other containers
  # (the provider's stand-in, the customers, CI, the git server) is not left here to be read.
  for f in /opt/seedco/*; do
    case "$(basename "$f")" in seat.sh|team_mcp.py) ;; *) rm -f "$f" ;; esac
  done
  for r in /work/*/; do
    n=$(basename "$r")
    git -C "$r" remote remove origin 2>/dev/null
    git -C "$r" remote add origin "http://$SEAT:$SEAT_TOKEN@git:8080/$n.git"
    git -C "$r" config user.name "$SEAT" && git -C "$r" config user.email "$SEAT@example.com"
    git -C "$r" fetch -q origin 2>/dev/null && git -C "$r" branch -q --set-upstream-to=origin/main main 2>/dev/null
  done
fi
touch /tmp/seat-ready      # the seat is as its holder should find it
[ -x /entrypoint.sh ] || exec "$@"
exec /entrypoint.sh "$@"
