import socket

_original_getaddrinfo = socket.getaddrinfo


def force_ipv4() -> None:
    """Make DNS resolution in this process return IPv4 addresses only.

    CDP's Secret API Key portal only allows a single allowlisted IP, but
    api.cdp.coinbase.com also resolves via AAAA — on a dual-stack connection
    Windows may route over IPv6, which never matches the allowlist and
    surfaces as an opaque 401. Call this once, before any CdpClient is
    created, to keep outbound requests on the allowlisted IPv4 address.
    """

    def ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = ipv4_only_getaddrinfo
