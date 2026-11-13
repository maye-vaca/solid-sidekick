# Manual host mapping

Requested execution: `{{EXECUTION_REQUEST}}`. This adapter supports manual only.
Follow the [shared capability contract]({{SKILL_PATH}}/references/host-capabilities.md).

The assistant proposes files/patches and commands; the user reviews and runs
them in an approved environment, then supplies actual results. Do not use
assistant execution tools for CAD in this mode, even if they are available.
This is an instruction boundary, not a filesystem sandbox or a permission grant.

Open the generated review.html yourself in a normal browser. For checked
updates, choose Load newer review and select the verified packet. Only you
choose Apply. The assistant must distinguish user-run validation, user-opened
review and unobserved inspection from its own execution.

If files cannot be attached, provide source/commands for manual copying rather
than fabricated download links. Do not assume remote paths are local paths.
Do not bypass a denied operation by asking another tool/host to perform it.
