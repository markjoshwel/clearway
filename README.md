clearway is a fan-in consumer for the «clearway for {teams, gmail, protonmail, whatsapp, telegram}» bridge adaptors (“producers”)

and is in charge of handling messaging IO as a subsystem leader of oversight (an orchestrator for a message triaging and forwarding system)

clearway-and-bridges (“consumer-producers”) communicate with an at-least-once delivery with an exactly-once effect, with idempotence handled on both ends of a duplex channel, alongside requests being deduped within a certain window

inbound messages do not fan out, communication responses only correspond to one conversation, on one producer
(e.g. a response to whatsapp does not need to go anywhere other than the clearway-for-whatsapp bridge)

clearway and it's bridges operate with a unified data model with three clearway-global identifiers, “entity_id”, “event_id”,  and “message_id”.
bridges (“producers”) then map the unified models onto underlying platform-specific data shapes to perform operations

all keys are symmetrically encrypted at rest to deter filesystem attacks; consumer-producers initially do the pqxdh (post-quantum extended diffie-hellman) key agreement protocol to establish e2ee communication over rest as ipc to deter mitm through local binaries and/or traffic sniffing

security acknowledgement: each process should be:
1. deployed such to be sandboxed with least-privileges,
2. have os-level ipc peer identity to only allow bridges and clearway, no one else to communicate
