import os
import tarfile
import zipfile
import time
import random
import magic  # python-magic zur Dateityperkennung
import pefile  # für Windows PE-Check und Signatur
import pyclamd  # ClamAV Python Client
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Version

@shared_task
def start_background_check(version_id):
    try:
        version = Version.objects.get(id=version_id)
    except Version.DoesNotExist:
        return

    # Schritt 0: Markiere Start
    version.checking_status = 'running'
    version.checking_log = ''
    version.save()

    file_path = version.file.path
    log = []

    try:
        # 1. Dateityp ermitteln
        mime = magic.from_file(file_path, mime=True)
        log.append(f"Mime-Type: {mime}")
        ext = os.path.splitext(file_path)[1].lower()
        time.sleep(random.randint(1, 3) * 60)  # 1-3 Minuten Verzögerung

        # 2. Spezifische Prüfungen je Format
        if ext == '.exe':
            # PE-Struktur und Signatur prüfen
            try:
                pe = pefile.PE(file_path)
                log.append(f"PE EntryPoint: {hex(pe.OPTIONAL_HEADER.AddressOfEntryPoint)}")
                if hasattr(pe, 'DIRECTORY_ENTRY_SECURITY'):
                    log.append("Digitales Zertifikat gefunden.")
                else:
                    log.append("Kein digitales Zertifikat.")
                pe.close()
            except pefile.PEFormatError as e:
                version.checking_status = 'failed'
                version.approved = False
                version.checking_log = f"Ungültige EXE: {e}"
                version.save()
                return
        elif ext in ['.ipa', '.apk', '.aab']:
            # ZIP-Archive prüfen
            try:
                with zipfile.ZipFile(file_path, 'r') as z:
                    names = z.namelist()
                    log.append(f"Archive enthält {len(names)} Dateien.")
                    comp_size = sum(info.compress_size for info in z.infolist())
                    uncomp_size = sum(info.file_size for info in z.infolist())
                    if comp_size and uncomp_size / comp_size > 100:
                        raise zipfile.BadZipFile('Mögliche ZIP-Bomb')
                    if ext == '.ipa' and not any(n.startswith('Payload/') for n in names):
                        raise zipfile.BadZipFile('Fehlender Payload-Ordner')
                    if ext in ['.apk', '.aab'] and 'AndroidManifest.xml' not in names:
                        raise zipfile.BadZipFile('Fehlende AndroidManifest.xml')
                    for n in names:
                        if '..' in n or n.startswith('/'):
                            raise zipfile.BadZipFile(f'Unsichere Pfad-Referenz: {n}')
            except zipfile.BadZipFile as e:
                version.checking_status = 'failed'
                version.approved = False
                version.checking_log = f"Ungültiges ZIP-Archiv: {e}"
                version.save()
                return
        elif ext in ['.tar.gz', '.tgz']:
            try:
                with tarfile.open(file_path, 'r:gz') as tar:
                    members = tar.getmembers()
                    log.append(f"tar.gz enthält {len(members)} Einträge.")
                    for m in members:
                        if m.name.startswith('/') or '..' in m.name:
                            raise Exception(f'Unsichere Pfad-Referenz: {m.name}')
            except Exception as e:
                version.checking_status = 'failed'
                version.approved = False
                version.checking_log = f"Fehler beim Entpacken tar.gz: {e}"
                version.save()
                return
        else:
            version.checking_status = 'failed'
            version.approved = False
            version.checking_log = f"Unbekannter Dateityp: {ext}"
            version.save()
            return

        time.sleep(random.randint(1, 3) * 60)  # weitere 1-3 Minuten Verzögerung

        # 3. Malware-Scan
        try:
            cd = pyclamd.ClamdNetworkSocket()
            if cd.ping():
                scan = cd.scan_file(file_path)
                if scan:
                    version.checking_status = 'failed'
                    version.approved = False
                    version.checking_log = f"Malware erkannt: {scan}"
                    version.save()
                    return
                else:
                    log.append("Kein Malware-Fund.")
        except Exception as e:
            log.append(f"Warnung Malware-Scan fehlgeschlagen: {e}")

        time.sleep(random.randint(1, 3) * 60)  # wieder 1-3 Minuten Verzögerung

        # 4. Inhaltsprüfung: Größe
        size = os.path.getsize(file_path)
        log.append(f"Dateigröße: {size} Bytes")
        if size > 500 * 1024 * 1024:
            version.checking_status = 'failed'
            version.approved = False
            version.checking_log = "Datei > 500MB"
            version.save()
            return

        time.sleep(random.randint(1, 3) * 60)  # nochmal 1-3 Minuten Verzögerung

        # 5. Simuliere Abschluss: kurze Wartezeit
        time.sleep(random.randint(1, 2) * 60)

        # Ergebnis speichern
        version.checking_status = 'passed'
        version.approved = True
        version.checking_log = "Erfolgreich geprüft:\n" + "\n".join(log)
        version.save()

        # Verzögerte Veröffentlichung 15-30 Minuten nach Zulassung
        delay_minutes = random.randint(15, 30)
        publish_time = timezone.now() + timedelta(minutes=delay_minutes)
        version.app.published = True
        version.app.published_at = publish_time
        version.app.save()

    except Exception as e:
        version.checking_status = 'failed'
        version.approved = False
        version.checking_log = f"Unerwarteter Fehler: {e}"
        version.save()


@shared_task
def start_background_check_version(version_id):
    try:
        version = Version.objects.get(id=version_id)
    except Version.DoesNotExist:
        return

    # Schritt 0: Markiere Start
    version.checking_status = 'running'
    version.checking_log = ''
    version.save()

    file_path = version.file.path
    log = []

    try:
        # 1. Dateityp ermitteln
        mime = magic.from_file(file_path, mime=True)
        log.append(f"Mime-Type: {mime}")
        ext = os.path.splitext(file_path)[1].lower()
        time.sleep(random.randint(1, 3) * 60)  # 1-3 Minuten Verzögerung

        # 2. Spezifische Prüfungen je Format
        if ext == '.exe':
            # PE-Struktur und Signatur prüfen
            try:
                pe = pefile.PE(file_path)
                log.append(f"PE EntryPoint: {hex(pe.OPTIONAL_HEADER.AddressOfEntryPoint)}")
                if hasattr(pe, 'DIRECTORY_ENTRY_SECURITY'):
                    log.append("Digitales Zertifikat gefunden.")
                else:
                    log.append("Kein digitales Zertifikat.")
                pe.close()
            except pefile.PEFormatError as e:
                version.checking_status = 'failed'
                version.approved = False
                version.checking_log = f"Ungültige EXE: {e}"
                version.save()
                return
        elif ext in ['.ipa', '.apk', '.aab']:
            # ZIP-Archive prüfen
            try:
                with zipfile.ZipFile(file_path, 'r') as z:
                    names = z.namelist()
                    log.append(f"Archive enthält {len(names)} Dateien.")
                    comp_size = sum(info.compress_size for info in z.infolist())
                    uncomp_size = sum(info.file_size for info in z.infolist())
                    if comp_size and uncomp_size / comp_size > 100:
                        raise zipfile.BadZipFile('Mögliche ZIP-Bomb')
                    if ext == '.ipa' and not any(n.startswith('Payload/') for n in names):
                        raise zipfile.BadZipFile('Fehlender Payload-Ordner')
                    if ext in ['.apk', '.aab'] and 'AndroidManifest.xml' not in names:
                        raise zipfile.BadZipFile('Fehlende AndroidManifest.xml')
                    for n in names:
                        if '..' in n or n.startswith('/'):
                            raise zipfile.BadZipFile(f'Unsichere Pfad-Referenz: {n}')
            except zipfile.BadZipFile as e:
                version.checking_status = 'failed'
                version.approved = False
                version.checking_log = f"Ungültiges ZIP-Archiv: {e}"
                version.save()
                return
        elif ext in ['.tar.gz', '.tgz']:
            try:
                with tarfile.open(file_path, 'r:gz') as tar:
                    members = tar.getmembers()
                    log.append(f"tar.gz enthält {len(members)} Einträge.")
                    for m in members:
                        if m.name.startswith('/') or '..' in m.name:
                            raise Exception(f'Unsichere Pfad-Referenz: {m.name}')
            except Exception as e:
                version.checking_status = 'failed'
                version.approved = False
                version.checking_log = f"Fehler beim Entpacken tar.gz: {e}"
                version.save()
                return
        else:
            version.checking_status = 'failed'
            version.approved = False
            version.checking_log = f"Unbekannter Dateityp: {ext}"
            version.save()
            return

        time.sleep(random.randint(1, 3) * 60)  # weitere 1-3 Minuten Verzögerung

        # 3. Malware-Scan
        try:
            cd = pyclamd.ClamdNetworkSocket()
            if cd.ping():
                scan = cd.scan_file(file_path)
                if scan:
                    version.checking_status = 'failed'
                    version.approved = False
                    version.checking_log = f"Malware erkannt: {scan}"
                    version.save()
                    return
                else:
                    log.append("Kein Malware-Fund.")
        except Exception as e:
            log.append(f"Warnung Malware-Scan fehlgeschlagen: {e}")

        time.sleep(random.randint(1, 3) * 60)  # wieder 1-3 Minuten Verzögerung

        # 4. Inhaltsprüfung: Größe
        size = os.path.getsize(file_path)
        log.append(f"Dateigröße: {size} Bytes")
        if size > 500 * 1024 * 1024:
            version.checking_status = 'failed'
            version.approved = False
            version.checking_log = "Datei > 500MB"
            version.save()
            return

        time.sleep(random.randint(1, 3) * 60)  # nochmal 1-3 Minuten Verzögerung

        # 5. Simuliere Abschluss: kurze Wartezeit
        time.sleep(random.randint(1, 2) * 60)

        # Ergebnis speichern
        version.checking_status = 'passed'
        version.approved = True
        version.checking_log = "Erfolgreich geprüft:\n" + "\n".join(log)
        version.save()

    except Exception as e:
        version.checking_status = 'failed'
        version.approved = False
        version.checking_log = f"Unerwarteter Fehler: {e}"
        version.save()