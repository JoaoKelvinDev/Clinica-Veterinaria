"""Provisionamento local explícito, sem cadastro público ou envio de convites."""

import argparse
import getpass
import os
from urllib.parse import urlparse
from uuid import UUID, uuid4

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.modules.clinics.models import Clinic, Role, User
from app.modules.clinics.schemas import ClinicUpdate, UserUpdate
from app.modules.clinics.services import BRAZIL_STATES


def main() -> None:
    parser = argparse.ArgumentParser(description="Criar clínica/usuário no Supabase local")
    parser.add_argument("--clinic-name")
    parser.add_argument("--clinic-id", type=UUID)
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", choices=list(Role), default=Role.ADMIN)
    parser.add_argument("--crmv")
    parser.add_argument("--crmv-state")
    args = parser.parse_args()
    base_url = os.environ["SUPABASE_URL"].rstrip("/")
    db_url = os.environ["MIGRATION_DATABASE_URL"]
    if any(urlparse(url).hostname not in {"localhost", "127.0.0.1"} for url in (base_url, db_url)):
        parser.error("Este comando aceita exclusivamente instâncias locais.")
    role = Role(args.role)
    name = UserUpdate(name=args.name, crmv=args.crmv).name
    state = args.crmv_state.upper() if args.crmv_state else None
    if state and state not in BRAZIL_STATES:
        parser.error("UF inválida")
    if role == Role.VETERINARIAN and (not args.crmv or not state):
        parser.error("Veterinário precisa de CRMV e UF")
    if not args.clinic_id and (not args.clinic_name or role != Role.ADMIN):
        parser.error("Para uma nova clínica, informe --clinic-name e use o papel admin")
    clinic_name = ClinicUpdate(name=args.clinic_name).name if not args.clinic_id else None
    if "@" not in args.email or len(args.email) > 254:
        parser.error("Informe um e-mail válido")
    engine = create_engine(db_url, hide_parameters=True)
    with Session(engine) as session:
        clinic = session.get(Clinic, args.clinic_id) if args.clinic_id else None
        if args.clinic_id and (clinic is None or clinic.deleted_at is not None):
            parser.error("Clínica não encontrada")
        secret_key = os.environ["SUPABASE_SECRET_KEY"]
        headers = {"apikey": secret_key, "Authorization": f"Bearer {secret_key}"}
        with httpx.Client(base_url=f"{base_url}/auth/v1", headers=headers, timeout=10) as client:
            response = client.get("/admin/users", params={"page": 1, "per_page": 1000})
            response.raise_for_status()
            identities = response.json().get("users", [])
            identity = next(
                (
                    item
                    for item in identities
                    if item.get("email", "").lower() == args.email.lower()
                ),
                None,
            )
            if identity:
                existing = session.scalar(select(User).where(User.auth_id == UUID(identity["id"])))
                if existing:
                    if args.clinic_id and existing.clinic_id != args.clinic_id:
                        parser.error("Este usuário já está vinculado a outra clínica")
                    print(f"Usuário já provisionado. Clínica: {existing.clinic_id}")
                    return
            else:
                password = os.getenv("BOOTSTRAP_PASSWORD") or getpass.getpass(
                    "Senha (mínimo 12 caracteres): "
                )
                if len(password) < 12:
                    parser.error("Use uma senha de pelo menos 12 caracteres")
                response = client.post(
                    "/admin/users",
                    json={"email": args.email, "password": password, "email_confirm": True},
                )
                if response.status_code not in {200, 201}:
                    parser.error("Não foi possível criar a identidade no Supabase local")
                identity = response.json()
        if clinic is None:
            clinic_id = uuid4()
            clinic = Clinic(id=clinic_id, clinic_id=clinic_id, name=clinic_name)
            session.add(clinic)
            session.flush()
        session.add(
            User(
                clinic_id=clinic.id,
                auth_id=UUID(identity["id"]),
                name=name,
                role=role,
                active=True,
                crmv=args.crmv,
                crmv_state=state,
            )
        )
        session.commit()
        print(f"Usuário provisionado sem envio de e-mail. Clínica: {clinic.id}")


if __name__ == "__main__":
    main()
