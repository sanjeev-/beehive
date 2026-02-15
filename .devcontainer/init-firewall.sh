#!/usr/bin/env bash
# init-firewall.sh — Default-deny outbound firewall for Beehive devcontainer.
# Allows HTTPS to services agents need (Anthropic API, GitHub, package registries).
# Blocks all other outbound traffic.
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

# HTTPS (443) — allow outbound to any destination.
# Previous approach resolved IPs via `dig` at init time, but CDN services
# (GitHub, Anthropic, npm, PyPI) use dynamic IPs that rotate after init,
# causing silent timeouts on git push / API calls. Allowing 443 broadly is
# standard for dev containers; the real protection is default-deny on all
# other ports and protocols.
iptables -A OUTPUT -p tcp --dport 443 -j ACCEPT

# SSH (22) to GitHub — for git-over-SSH fallback.
# GitHub publishes their IP ranges; fetch them from the meta API.
# Fall back to dig if the API call fails.
gh_ips=""
meta=$(curl -sf --max-time 5 https://api.github.com/meta 2>/dev/null) && \
    gh_ips=$(echo "$meta" | grep -oE '"[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/[0-9]+"' | tr -d '"') || true

if [ -n "$gh_ips" ]; then
    for cidr in $gh_ips; do
        iptables -A OUTPUT -p tcp --dport 22 -d "$cidr" -j ACCEPT
    done
else
    # Fallback: resolve github.com via DNS
    for ip in $(dig +short github.com 2>/dev/null); do
        iptables -A OUTPUT -p tcp --dport 22 -d "$ip" -j ACCEPT
    done
fi

# Log blocked packets for debugging (rate-limited)
iptables -A OUTPUT -m limit --limit 5/min -j LOG --log-prefix "BEEHIVE-BLOCKED: " --log-level 4

echo "Beehive firewall initialised — default-deny outbound, HTTPS + DNS allowed."
