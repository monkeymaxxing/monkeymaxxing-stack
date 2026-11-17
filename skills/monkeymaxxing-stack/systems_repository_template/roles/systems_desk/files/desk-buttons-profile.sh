# The person's own SSH agent on this desk. The systems_desk role installs
# this template as /etc/profile.d/desk-buttons.sh.
# It holds the production key: a plain git push of the person's
# reaches the main copy on util01 with it. Git's SSH takes the agent
# only from SSH_AUTH_SOCK, and the person's SSH login from the laptop brings
# none. The coding agent's values come from sshd (sshd.conf, SetEnv).
if [ "$(id -un)" = "{{ .inputs.person_unix_username }}" ]; then
    export SSH_AUTH_SOCK=/run/desk-ssh-agent/private.sock
fi
