def has_role(user, roles):
    if not user or not user.is_authenticated:
        return False

    # current single role field (your existing system)
    if getattr(user, "role", None) in roles:
        return True

    # dynamic roles via groups
    return user.groups.filter(name__in=roles).exists()
