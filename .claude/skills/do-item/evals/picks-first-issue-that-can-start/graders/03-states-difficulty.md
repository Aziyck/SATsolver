---
type: regex
# "#23" with the hash appears only in the session's own text: the fixture's
# JSON names issues as "number":23, so reading it cannot satisfy this.
pattern: '#23[^\n]{0,300}\bmedium\b|\bmedium\b[^\n]{0,300}#23'
flags: i
target: trace
---
