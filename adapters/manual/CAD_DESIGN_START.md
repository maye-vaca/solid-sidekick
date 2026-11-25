# Manual / bring-your-own-assistant startup

Ask your assistant to read [the complete skill]({{SKILL_PATH}}/SKILL.md) and its
[public API]({{SKILL_PATH}}/references/public-api.md).
If it cannot read local files, supply the relevant instructions explicitly;
file upload does not grant execution access to your computer.

The skill is the single source of design and revision behavior.
Before modeling or resuming, read the prototype and assembly evidence policy in the [operating model]({{SKILL_PATH}}/references/operating-model.md); supply that policy explicitly if local files are unavailable.
Read [the manual-mode guide]({{HOST_GUIDE}}) and
[capability contract]({{SKILL_PATH}}/references/host-capabilities.md).
The assistant proposes inspectable changes; you run approved commands and return
actual results. It must not claim execution or local access it does not have.
No automatic agent discovery, model connection or dependency installation is
provided. Do not run generated code without reviewing it and its requested scope.
