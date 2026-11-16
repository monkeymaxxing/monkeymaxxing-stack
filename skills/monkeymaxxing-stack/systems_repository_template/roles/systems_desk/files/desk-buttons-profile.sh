# Each login's SSH agent on this desk. The systems_desk role installs this
# template as /etc/profile.d/desk-buttons.sh.
# The person starts any trusted agent with sudo -u coding-agent -i.
if [ "$(id -un)" = coding-agent ]; then
    export SSH_AUTH_SOCK=/run/desk-ssh-agent/socket
    # Git's system-level settings for the coding agent: Git reaches the Git
    # host through /etc/systems-desk/ssh.conf. A checkout's own
    # core.sshCommand, such as the app checkout's key, overrides it, which
    # GIT_SSH_COMMAND would not allow.
    export GIT_CONFIG_SYSTEM=/etc/systems-desk/coding-agent-gitconfig
fi
# The person's own agent, which holds the production key: a plain git commit
# in the person's systems repository signs with it, as the vault commits
# after mmx secrets set need. Git's SSH signing takes the agent only from
# SSH_AUTH_SOCK, and the person's SSH login from the laptop brings none.
if [ "$(id -un)" = "{{ .inputs.person_unix_username }}" ]; then
    export SSH_AUTH_SOCK=/run/desk-ssh-agent/private.sock
fi
