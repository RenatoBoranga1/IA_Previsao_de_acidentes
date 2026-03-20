from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RoleProfile:
    key: str
    title: str
    description: str
    permissions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UserRecord:
    id: str
    name: str
    email: str
    role: str
    password_hash: str
    active: bool = True

    def to_safe_dict(self) -> dict:
        role_profile = ROLE_PROFILES.get(self.role)
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "role_title": role_profile.title if role_profile else self.role,
            "permissions": list(role_profile.permissions) if role_profile else [],
            "active": self.active,
        }


ROLE_PROFILES: dict[str, RoleProfile] = {
    "admin": RoleProfile(
        key="admin",
        title="Administrador",
        description="Gerencia acessos, governanca e visoes administrativas do sistema.",
        permissions=("dashboard:view", "users:read", "auth:manage"),
    ),
    "gestor": RoleProfile(
        key="gestor",
        title="Gestor Operacional",
        description="Consulta previsoes, hotspots e prioridades executivas para tomada de decisao.",
        permissions=("dashboard:view",),
    ),
    "analista": RoleProfile(
        key="analista",
        title="Analista",
        description="Analisa previsoes, rankings e detalhamentos tecnicos do painel.",
        permissions=("dashboard:view",),
    ),
}
