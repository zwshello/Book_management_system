import uuid
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from borrowing.models import BorrowRecord
from borrowing.workflow import advance


class Command(BaseCommand):
    help = "Reconcile pending stock results by their original operation IDs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--min-age",
            type=int,
            default=5,
            help="Minimum seconds since last update; 0 for immediate recovery",
        )
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument(
            "--cancel-pending",
            help="UUID of a PENDING borrow to compensate after stock result is known",
        )

    def handle(self, *args, **options):
        if options["min_age"] < 0 or not 1 <= options["limit"] <= 1000:
            raise CommandError("min-age must be non-negative and limit 1..1000")
        cancel_id = options["cancel_pending"]
        if cancel_id:
            try:
                record_id = uuid.UUID(cancel_id)
                record = BorrowRecord.objects.get(pk=record_id)
            except (ValueError, BorrowRecord.DoesNotExist) as error:
                raise CommandError("Pending record not found") from error
            if record.status != BorrowRecord.Status.PENDING:
                raise CommandError("Only PENDING records can be compensated")
            changed = advance(record.pk, cancel=True)
            self.stdout.write(
                f"{changed.pk}: {changed.status} {changed.last_error_code}"
            )
            return
        cutoff = timezone.now() - timedelta(seconds=options["min_age"])
        ids = list(
            BorrowRecord.objects.filter(
                status__in=[
                    BorrowRecord.Status.PENDING,
                    BorrowRecord.Status.RETURN_PENDING,
                ],
                updated_at__lte=cutoff,
            )
            .order_by("updated_at", "id")
            .values_list("pk", flat=True)[: options["limit"]]
        )
        for record_id in ids:
            record = advance(record_id)
            self.stdout.write(f"{record.pk}: {record.status} {record.last_error_code}")
        self.stdout.write(f"Checked {len(ids)} pending record(s).")
