import csv
import logging
import re
from collections import OrderedDict
from datetime import datetime
from typing import Dict, List, Mapping, Tuple

from beancount.core import data
from beancount.core.amount import Amount
from beancount.core.number import Decimal
from beancount.ingest import importer

actions = [
    "PRLV EUROP PONCTUEL",
    "PRELEVEMENT EUROPEEN",
    "VIR RECU",
    "VIR INST REC",
    "VIR PERM",
    "VIR INSTANTANE EMIS",
    "VIR EUROPEEN EMIS",
    "PRELEVEMENT EUROPEEN",
    "VIREMENT RECU",
    "VIREMENT EMIS",
    "FRAIS VIR INSTANTANE",
    "CHEQUE",
    "REMISE CHEQUE",
]


class SoGImporter(importer.ImporterProtocol):
    def __init__(
        self,
        account: str,
        file_encoding: str = "latin-1",
    ):
        self.account = account
        self.file_encoding = file_encoding

    def _parse_date(self, entry, key: str = "Date de l'opération"):
        return datetime.strptime(entry[key], "%d/%m/%Y").date()

    def _split_libelle(self, libelle: str) -> Tuple[str, str, str]:
        if libelle.startswith("000001"):
            libelle = libelle[7:]

        for action in actions:
            if libelle.startswith(action):
                entry_action = action
                payee_and_ref = libelle[len(action) + 1 :].strip()
                break
        else:
            raise Exception(f"{libelle} unmatched")

        if entry_action in ("CHEQUE", "REMISE CHEQUE"):
            return entry_action, "TODO", libelle
        elif entry_action == "FRAIS VIR INSTANTANE":
            return entry_action, "SoG", libelle
        elif libelle.startswith("VIREMENT RECU PAR SOCIETE GENERALE"):
            return entry_action, "SoG", libelle
        elif libelle.startswith("VIREMENT EMIS PAR SOCIETE GENERALE"):
            return entry_action, "SoG", libelle

        for sep in ("DE:", "POUR:"):
            if sep in payee_and_ref:
                _, payee_and_ref = payee_and_ref.split(sep)
                for ref_sep in ("ID:", "MOTIF:"):
                    if ref_sep in payee_and_ref:
                        payee, reference = payee_and_ref.split(ref_sep)
                        return entry_action, payee.strip(), reference.strip()

        return entry_action, "TODO", libelle

    def _fix_payee(self, payee: str) -> str:
        if "DATE" in payee:
            payee = payee.split("DATE")[0].strip()
        if "REF" in payee:
            payee = payee.split("REF")[0].strip()
        if "BQ" in payee:
            payee = payee.split("BQ")[0][:-6].strip()
        return payee

    def identify(self, file_) -> bool:
        try:
            with open(file_.name, encoding=self.file_encoding) as fd:
                line = fd.readline().strip()
        except ValueError:
            return False
        return True

    def extract(self, file_, existing_entries=None):
        entries = []

        with open(file_.name, encoding=self.file_encoding) as fd:
            fd.readline()
            second_line = fd.readline().replace("\n", "")

            fd.seek(0)  # Reset

            fd.readline()  # Skip first line
            if second_line == "":
                fd.readline()
            reader = csv.DictReader(fd, delimiter=";", quoting=csv.QUOTE_MINIMAL)

            for index, line in enumerate(reader):
                meta = data.new_metadata(file_.name, index)

                amount_eur = Decimal(line["Montant de l'opération"].replace(",", "."))
                currency = "EUR"
                libelle = line["Détail de l'écriture"]
                date = self._parse_date(line)

                action, payee, reference = self._split_libelle(libelle)

                postings = [
                    data.Posting(
                        self.account,
                        Amount(amount_eur, currency),
                        None,
                        None,
                        None,
                        None,
                    ),
                ]

                entries.append(
                    data.Transaction(
                        meta,
                        date,
                        self.FLAG,
                        self._fix_payee(payee),
                        reference,
                        data.EMPTY_SET,
                        data.EMPTY_SET,
                        postings,
                    )
                )

        return entries
