#!/usr/bin/env bash
# init-firewall.sh — Default-deny outbound firewall for Beehive devcontainer.
# Only allows traffic to services agents actually need.
set -euo pipefail

# Flush existing rules
iptables -F OUTPUT

# Default deny outbound
iptables -P OUTPUT DROP

# Allow loopback (localhost)
iptables -A OUTPUT -o lo -j ACCEPT

# Allow established / related connections (responses to allowed requests)
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# DNS (UDP + TCP port 53)
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT

# HTTPS (443) — whitelisted hosts
for host in \
    api.anthropic.com \
    github.com \
    api.github.com \
    registry.npmjs.org \
    pypi.org \
    files.pythonhosted.org; do
    for ip in $(dig +short "$host" 2>/dev/null); do
        iptables -A OUTPUT -p tcp --dport 443 -d "$ip" -j ACCEPT
    done
done

# SSH (22) to github.com — for git over SSH
for ip in $(dig +short github.com 2>/dev/null); do
    iptables -A OUTPUT -p tcp --dport 22 -d "$ip" -j ACCEPT
done

# Log blocked packets for debugging (rate-limited)
iptables -A OUTPUT -m limit --limit 5/min -j LOG --log-prefix "BEEHIVE-BLOCKED: " --log-level 4

echo "Beehive firewall initialised — default-deny outbound with whitelisted services."
