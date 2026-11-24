-- the monaco-gertrude card gets no UCM profile from PipeWire (only off / pro-audio), so it
-- stays "off" and the desktop only has a Dummy Output. Use pro-audio and prefer PCM 0 (MAX98091,
-- routed to Line Out = Waveshare carrier speakers by lineout.service).
table.insert(alsa_monitor.rules, {
  matches = { { { "device.name", "equals", "alsa_card.platform-sound" } } },
  apply_properties = { ["device.profile"] = "pro-audio" },
})
table.insert(alsa_monitor.rules, {
  matches = { { { "node.name", "equals", "alsa_output.platform-sound.pro-output-0" } } },
  apply_properties = {
    ["priority.session"] = 2000, ["priority.driver"] = 2000, ["node.description"] = "Speakers (Line Out)",
    -- never close the PCM when idle: every open/close powers the codec output stage up/down,
    -- which is an audible pop on the speakers
    ["session.suspend-timeout-seconds"] = 0,
  },
})
