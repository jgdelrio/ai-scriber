"""
Management command to manually check for stuck processing files.
This is useful for testing the S3 safeguard mechanism.
"""
from django.core.management.base import BaseCommand
from apps.core.tasks import check_stuck_processing_files


class Command(BaseCommand):
    help = 'Manually check for stuck processing files and attempt recovery via S3'

    def handle(self, *args, **options):
        self.stdout.write("Checking for stuck processing files...")
        
        try:
            result = check_stuck_processing_files()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Stuck file check completed: "
                    f"Checked {result['checked_files']} files, "
                    f"Recovered {result['recovered_files']} files"
                )
            )
            
            if result['recovered_files'] > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Successfully recovered {result['recovered_files']} stuck files!"
                    )
                )
            else:
                self.stdout.write("No stuck files found or no files could be recovered.")
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error during stuck file check: {e}")
            )
            raise