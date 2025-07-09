import os
import tarfile
import zipfile
import time
import random
import magic
import pefile
import pyclamd
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.core.mail import EmailMultiAlternatives
from .models import Version, Notification, App
from django.template.loader import render_to_string
from django.conf import settings

def create_notification(user, title, message, app=None, version=None, level='info'):
    """
    Erstellt eine Benachrichtigung für den Nutzer.

    Args:
        user: Der User, dem die Notification gehört
        title: Titel der Benachrichtigung
        message: Textinhalt
        app: (Optional) Die zugehörige App
        version: (Optional) Die zugehörige App-Version
        level: info / success / warning / error
    """
    Notification.objects.create(
        user=user,
        title=title,
        message=message,
        app=app,
        version=version,
        level=level,
        timestamp=timezone.now()
    )

def send_check_email(user, subject, message, log_lines, app=None, version=None, success=False, error_msg=None):
    """
    Sendet eine E-Mail mit HTML-Template, inkl. App-Logo, Log als Text im HTML und Fehlermeldung.

    Args:
      user: User-Objekt (hat .email)
      subject: Betreff der Mail
      message: Haupttext (string, ausführliche Beschreibung)
      log_lines: Liste von Log-Zeilen (werden im HTML als Text ausgegeben)
      app: optionale App-Instanz (für Template)
      version: optionale Version-Instanz (für Template)
      success: bool, ob Prüfung erfolgreich war (für Anzeige Button)
      error_msg: optionale Fehlermeldung, wird prominent im Text angezeigt
    """
    # Kombiniere Log in einen String für HTML-Ausgabe
    log_text = "\n".join(log_lines)

    # Lade die neuesten veröffentlichten Apps
    new_apps = App.objects.filter(
        published=True,
        published_at__isnull=False
    ).order_by('-published_at')[:6]


    # Erzeuge HTML aus Template
    html_content = render_to_string('emails/notification.html', {
        'user': user,
        'subject': subject,
        'message': message,
        'log_text': log_text,
        'app': app,
        'version': version,
        'success': success,
        'error_msg': error_msg,
        'appstore_logo_url': settings.APPSTORE_LOGO_URL,  # z. B. /static/images/logo.png
        'new_apps': new_apps,
    })

    # Plain-Text Version (vereinfacht)
    text_content = f"{message}\n\nPrüfprotokoll:\n{log_text}"
    if error_msg:
        text_content += f"\n\nFEHLER:\n{error_msg}"

    msg = EmailMultiAlternatives(subject, text_content, to=[user.email])
    msg.attach_alternative(html_content, "text/html")
    msg.send()

@shared_task
def start_background_check(version_id):
    try:
        version = Version.objects.get(id=version_id)
    except Version.DoesNotExist:
        return

    version.checking_status = 'running'
    version.checking_log = ''
    version.save()

    file_path = version.file.path
    log = []
    dev = version.app.developer

    def fail(msg):
        log.append(f"*** FEHLER: {msg}")
        version.checking_status = 'failed'
        version.approved = False
        version.checking_log = "\n".join(log) + "\n\nFEHLER: " + msg
        version.save()
        send_check_email(
            user=dev,
            subject=f"Prüfung fehlgeschlagen: {version.app.name}",
            message="Die App-Prüfung ist fehlgeschlagen.",
            log_lines=log,
            app=version.app,
            version=version,
            success=False,
            error_msg=msg
        )
        create_notification(
            user=dev.user,
            title=f"Prüfung fehlgeschlagen: {version.app.name}",
            message=msg,
            app=version.app,
            version=version,
            level='error'
        )

    try:
        log.append(f"Starte Prüfung für Datei: {file_path}")

        mime = magic.from_file(file_path, mime=True)
        log.append(f"Ermittelter MIME-Type: {mime}")

        ext = os.path.splitext(file_path)[1].lower()
        log.append(f"Dateiendung: {ext}")

        size = os.path.getsize(file_path)
        log.append(f"Dateigröße: {size} Bytes")
        if size > 500 * 1024 * 1024:
            return fail("Datei ist größer als 500MB.")

        time.sleep(random.randint(1, 3) * 60)

        if ext == '.exe':
            log.append("Prüfe EXE-Datei (PE-Analyse).")
            try:
                pe = pefile.PE(file_path)
                log.append(f"PE EntryPoint: {hex(pe.OPTIONAL_HEADER.AddressOfEntryPoint)}")
                if hasattr(pe, 'DIRECTORY_ENTRY_SECURITY') and pe.DIRECTORY_ENTRY_SECURITY:
                    log.append("Digitales Zertifikat gefunden.")
                else:
                    log.append("Kein digitales Zertifikat gefunden.")
                pe.close()
            except pefile.PEFormatError as e:
                return fail(f"Ungültige EXE-Datei: {e}")

        elif ext in ['.ipa', '.apk', '.aab']:
            log.append(f"Prüfe ZIP-Archiv mit Endung {ext}.")
            try:
                with zipfile.ZipFile(file_path, 'r') as z:
                    names = z.namelist()
                    log.append(f"ZIP-Archiv enthält {len(names)} Dateien.")
                    comp_size = sum(info.compress_size for info in z.infolist())
                    uncomp_size = sum(info.file_size for info in z.infolist())
                    log.append(f"Komprimierte Größe: {comp_size}, Unkomprimierte Größe: {uncomp_size}")
                    if comp_size and uncomp_size / comp_size > 100:
                        return fail("Verdacht auf ZIP-Bombe: Verhältnis unkomprimiert zu komprimiert zu hoch.")
                    if ext == '.ipa' and not any(n.startswith('Payload/') for n in names):
                        return fail("Fehlender Payload-Ordner in IPA.")
                    if ext in ['.apk', '.aab'] and 'AndroidManifest.xml' not in names:
                        return fail("Fehlende AndroidManifest.xml in APK/AAB.")
                    for n in names:
                        if '..' in n or n.startswith('/'):
                            return fail(f"Unsichere Pfad-Referenz im Archiv: {n}")
            except zipfile.BadZipFile as e:
                return fail(f"Ungültiges ZIP-Archiv: {e}")

        elif ext in ['.tar.gz', '.tgz']:
            log.append("Prüfe tar.gz-Archiv.")
            try:
                with tarfile.open(file_path, 'r:gz') as tar:
                    members = tar.getmembers()
                    log.append(f"tar.gz enthält {len(members)} Einträge.")
                    for m in members:
                        if m.name.startswith('/') or '..' in m.name:
                            return fail(f"Unsichere Pfad-Referenz im tar.gz: {m.name}")
            except Exception as e:
                return fail(f"Fehler beim Entpacken des tar.gz: {e}")

        elif ext == '.gz':
            log.append("Prüfe .gz-Datei, versuche Entpacken.")
            try:
                import gzip, shutil
                temp_out = file_path + '_ungzipped'
                with gzip.open(file_path, 'rb') as f_in, open(temp_out, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
                log.append(f".gz entpackt: {temp_out}")
                if temp_out.endswith('.ipa') or zipfile.is_zipfile(temp_out):
                    with zipfile.ZipFile(temp_out, 'r') as z:
                        names = z.namelist()
                        log.append(f"Entpacktes Archiv enthält {len(names)} Dateien.")
                        if not any(n.startswith('Payload/') for n in names):
                            return fail("Entpackte IPA fehlt Payload-Ordner.")
                else:
                    log.append("Keine ZIP-Struktur erkannt.")
                os.remove(temp_out)
            except Exception as e:
                return fail(f"Fehler beim Entpacken der .gz-Datei: {e}")

        else:
            return fail(f"Unbekannter oder nicht erlaubter Dateityp: {ext}")

        time.sleep(random.randint(1, 3) * 60)

        try:
            log.append("Starte Virenscan mit ClamAV.")
            cd = pyclamd.ClamdNetworkSocket()
            if not cd.ping():
                log.append("Warnung: ClamAV nicht erreichbar.")
            else:
                scan = cd.scan_file(file_path)
                if scan:
                    return fail(f"Malware erkannt: {scan}")
                else:
                    log.append("Kein Malware-Fund im Scan.")
        except Exception as e:
            log.append(f"Virenscan-Fehler: {e}")

        time.sleep(random.randint(1, 3) * 60)
        time.sleep(random.randint(1, 2) * 60)

        version.checking_status = 'passed'
        version.approved = True
        version.checking_log = "Erfolgreich geprüft:\n" + "\n".join(log)
        version.save()

        subject = f"{version.app.name} wurde erfolgreich geprüft"
        message = f"Die Version {version.version_number} Ihrer App wurde erfolgreich geprüft und freigegeben."
        send_check_email(dev, subject, message, log)
        create_notification(
            user=dev.user,
            title=f"Prüfung erfolgreich: {version.app.name}",
            message=message,
            app=version.app,
            version=version,
            level='success_1'
        )

        time.sleep(random.randint(15, 20) * 60)

        version.app.published = True
        version.app.save()

        send_check_email(dev,
            f"{version.app.name} ist jetzt veröffentlicht",
            "Ihre App wurde soeben freigegeben und ist jetzt öffentlich sichtbar.",
            log
        )
        create_notification(
            user=dev.user,
            title=f"{version.app.name} ist jetzt veröffentlicht",
            message="Ihre App wurde soeben freigegeben und ist jetzt öffentlich sichtbar.",
            app=version.app,
            version=version,
            level='success_2'
        )

    except Exception as e:
        error_message = f"Unerwarteter Fehler: {e}"
        version.checking_status = 'failed'
        version.approved = False
        version.checking_log = "\n".join(log) + "\n\nFEHLER: " + error_message
        version.save()
        send_check_email(
            user=dev,
            subject=f"Unerwarteter Fehler bei der Prüfung: {version.app.name}",
            message="Die App-Prüfung ist aufgrund eines unerwarteten Fehlers fehlgeschlagen.",
            log_lines=log,
            app=version.app,
            version=version,
            success=False,
            error_msg=error_message
        )
        create_notification(
            user=dev.user,
            title=f"Prüfung fehlgeschlagen: {version.app.name}",
            message=error_message,
            app=version.app,
            version=version,
            level='error'
        )




@shared_task
def start_background_check_version(version_id):
    try:
        version = Version.objects.get(id=version_id)
    except Version.DoesNotExist:
        return

    version.checking_status = 'running'
    version.checking_log = ''
    version.save()

    file_path = version.file.path
    log = []
    dev = version.app.developer

    def fail(msg):
        log.append(f"*** FEHLER: {msg}")
        version.checking_status = 'failed'
        version.approved = False
        version.checking_log = "\n".join(log) + "\n\nFEHLER: " + msg
        version.save()
        send_check_email(
            user=dev,
            subject=f"Prüfung fehlgeschlagen: {version.app.name}",
            message="Die App-Prüfung ist fehlgeschlagen.",
            log_lines=log,
            app=version.app,
            version=version,
            success=False,
            error_msg=msg
        )
        create_notification(
            user=dev.user,
            title=f"Prüfung fehlgeschlagen: {version.app.name}",
            message=msg,
            app=version.app,
            version=version,
            level='error'
        )

    try:
        log.append(f"Starte Prüfung für Datei: {file_path}")

        mime = magic.from_file(file_path, mime=True)
        log.append(f"Ermittelter MIME-Type: {mime}")

        ext = os.path.splitext(file_path)[1].lower()
        log.append(f"Dateiendung: {ext}")

        size = os.path.getsize(file_path)
        log.append(f"Dateigröße: {size} Bytes")
        if size > 500 * 1024 * 1024:
            return fail("Datei ist größer als 500MB.")

        time.sleep(random.randint(1, 3) * 60)

        if ext == '.exe':
            log.append("Prüfe EXE-Datei (PE-Analyse).")
            try:
                pe = pefile.PE(file_path)
                log.append(f"PE EntryPoint: {hex(pe.OPTIONAL_HEADER.AddressOfEntryPoint)}")
                if hasattr(pe, 'DIRECTORY_ENTRY_SECURITY') and pe.DIRECTORY_ENTRY_SECURITY:
                    log.append("Digitales Zertifikat gefunden.")
                else:
                    log.append("Kein digitales Zertifikat gefunden.")
                pe.close()
            except pefile.PEFormatError as e:
                return fail(f"Ungültige EXE-Datei: {e}")

        elif ext in ['.ipa', '.apk', '.aab']:
            log.append(f"Prüfe ZIP-Archiv mit Endung {ext}.")
            try:
                with zipfile.ZipFile(file_path, 'r') as z:
                    names = z.namelist()
                    log.append(f"ZIP-Archiv enthält {len(names)} Dateien.")
                    comp_size = sum(info.compress_size for info in z.infolist())
                    uncomp_size = sum(info.file_size for info in z.infolist())
                    log.append(f"Komprimierte Größe: {comp_size}, Unkomprimierte Größe: {uncomp_size}")
                    if comp_size and uncomp_size / comp_size > 100:
                        return fail("Verdacht auf ZIP-Bombe: Verhältnis unkomprimiert zu komprimiert zu hoch.")
                    if ext == '.ipa' and not any(n.startswith('Payload/') for n in names):
                        return fail("Fehlender Payload-Ordner in IPA.")
                    if ext in ['.apk', '.aab'] and 'AndroidManifest.xml' not in names:
                        return fail("Fehlende AndroidManifest.xml in APK/AAB.")
                    for n in names:
                        if '..' in n or n.startswith('/'):
                            return fail(f"Unsichere Pfad-Referenz im Archiv: {n}")
            except zipfile.BadZipFile as e:
                return fail(f"Ungültiges ZIP-Archiv: {e}")

        elif ext in ['.tar.gz', '.tgz']:
            log.append("Prüfe tar.gz-Archiv.")
            try:
                with tarfile.open(file_path, 'r:gz') as tar:
                    members = tar.getmembers()
                    log.append(f"tar.gz enthält {len(members)} Einträge.")
                    for m in members:
                        if m.name.startswith('/') or '..' in m.name:
                            return fail(f"Unsichere Pfad-Referenz im tar.gz: {m.name}")
            except Exception as e:
                return fail(f"Fehler beim Entpacken des tar.gz: {e}")

        elif ext == '.gz':
            log.append("Prüfe .gz-Datei, versuche Entpacken.")
            try:
                import gzip, shutil
                temp_out = file_path + '_ungzipped'
                with gzip.open(file_path, 'rb') as f_in, open(temp_out, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
                log.append(f".gz entpackt: {temp_out}")
                if temp_out.endswith('.ipa') or zipfile.is_zipfile(temp_out):
                    with zipfile.ZipFile(temp_out, 'r') as z:
                        names = z.namelist()
                        log.append(f"Entpacktes Archiv enthält {len(names)} Dateien.")
                        if not any(n.startswith('Payload/') for n in names):
                            return fail("Entpackte IPA fehlt Payload-Ordner.")
                else:
                    log.append("Keine ZIP-Struktur erkannt.")
                os.remove(temp_out)
            except Exception as e:
                return fail(f"Fehler beim Entpacken der .gz-Datei: {e}")

        else:
            return fail(f"Unbekannter oder nicht erlaubter Dateityp: {ext}")

        time.sleep(random.randint(1, 3) * 60)

        try:
            log.append("Starte Virenscan mit ClamAV.")
            cd = pyclamd.ClamdNetworkSocket()
            if not cd.ping():
                log.append("Warnung: ClamAV nicht erreichbar.")
            else:
                scan = cd.scan_file(file_path)
                if scan:
                    return fail(f"Malware erkannt: {scan}")
                else:
                    log.append("Kein Malware-Fund im Scan.")
        except Exception as e:
            log.append(f"Virenscan-Fehler: {e}")

        time.sleep(random.randint(1, 3) * 60)
        time.sleep(random.randint(1, 2) * 60)

        version.checking_status = 'passed'
        version.approved = True
        version.checking_log = "Erfolgreich geprüft:\n" + "\n".join(log)
        version.save()

        subject = f"{version.app.name} wurde erfolgreich geprüft"
        message = f"Die Version {version.version_number} Ihrer App wurde erfolgreich geprüft und freigegeben."
        send_check_email(dev, subject, message, log)
        create_notification(
            user=dev.user,
            title=f"Prüfung erfolgreich: {version.app.name}",
            message=message,
            app=version.app,
            version=version,
            level='success_1'
        )

        time.sleep(random.randint(15, 20) * 60)

        version.app.published = True
        version.app.save()

        send_check_email(dev,
            f"{version.app.name} ist jetzt veröffentlicht",
            "Ihre App wurde soeben freigegeben und ist jetzt öffentlich sichtbar.",
            log
        )
        create_notification(
            user=dev.user,
            title=f"{version.app.name} ist jetzt veröffentlicht",
            message="Ihre App wurde soeben freigegeben und ist jetzt öffentlich sichtbar.",
            app=version.app,
            version=version,
            level='success_2'
        )

    except Exception as e:
        error_message = f"Unerwarteter Fehler: {e}"
        version.checking_status = 'failed'
        version.approved = False
        version.checking_log = "\n".join(log) + "\n\nFEHLER: " + error_message
        version.save()
        send_check_email(
            user=dev,
            subject=f"Unerwarteter Fehler bei der Prüfung: {version.app.name}",
            message="Die App-Prüfung ist aufgrund eines unerwarteten Fehlers fehlgeschlagen.",
            log_lines=log,
            app=version.app,
            version=version,
            success=False,
            error_msg=error_message
        )
        create_notification(
            user=dev.user,
            title=f"Prüfung fehlgeschlagen: {version.app.name}",
            message=error_message,
            app=version.app,
            version=version,
            level='error'
        )