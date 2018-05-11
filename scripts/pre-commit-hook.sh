#! /bin/sh

if ! python3 -m json.tool config.json >/dev/null; then
	echo "config.json isn't valid, aborting commit." >&2
	exit 1
fi
