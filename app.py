# -*- coding: utf-8 -*-
# HorizonBoard - Monday.com-ähnliches Projektmanagement-Tool
import os, uuid, shutil, sys, threading, time, webbrowser
from flask import Flask, render_template, request, redirect, url_for, flash, g, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Table, Column, Integer, String, Text, DateTime, Boolean, BigInteger, ForeignKey
from sqlalchemy.orm import relationship, joinedload
from datetime import datetime, date, timedelta
from collections import defaultdict
import locale
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

try:
    locale.setlocale(locale.LC_TIME, 'de_DE.utf8')
except:
    try:
        locale.setlocale(locale.LC_TIME, 'de_DE')
    except:
        pass

# --- Konstanten ---
AUFGABEN_STATUS = ["Startbereit", "In Bearbeitung", "Überprüfung ausstehend",
                   "Arbeitseinsatz ausstehend", "Erledigt", "Blockiert"]
STATUS_KLASSEN = {
    "Startbereit": "status-startbereit", "In Bearbeitung": "status-in-bearbeitung",
    "Überprüfung ausstehend": "status-ueberpruefung",
    "Arbeitseinsatz ausstehend": "status-arbeit",
    "Erledigt": "status-erledigt", "Blockiert": "status-blockiert",
}
PRIORITAETEN = ["Kritisch", "Hoch", "Mittel", "Niedrig"]
PRIO_KLASSEN = {"Kritisch": "prio-kritisch", "Hoch": "prio-hoch",
                "Mittel": "prio-mittel", "Niedrig": "prio-niedrig"}
AUFGABEN_TYPEN = ["Fehler", "Funktion", "Update", "Qualität"]
TYP_KLASSEN = {"Fehler": "typ-fehler", "Funktion": "typ-funktion",
               "Update": "typ-update", "Qualität": "typ-qualitaet"}
EPIC_PHASEN = ["Backlog", "Produkt Discovery", "Dev in Arbeit", "Erledigt", "Auf Eis gelegt"]
BUG_GRUPPEN = ["Eingehende Bugs", "Entwicklungsarbeiten", "Behoben", "In Sprints verwaltet"]
BUG_STATUS = ["Prüfung ausstehend", "In Bearbeitung", "Behoben", "Geschlossen"]
BUG_STATUS_KLASSEN = {
    "Prüfung ausstehend": "status-arbeit", "In Bearbeitung": "status-in-bearbeitung",
    "Behoben": "status-erledigt", "Geschlossen": "status-startbereit",
}
FEEDBACK_TYPEN = ["Diskussion", "Verbessern", "Behalten", "Aktion"]
FEEDBACK_KLASSEN = {"Diskussion": "feedback-diskussion", "Verbessern": "feedback-verbessern",
                    "Behalten": "feedback-behalten", "Aktion": "feedback-aktion"}

# --- Flask App ---
app = Flask(__name__)
if getattr(sys, 'frozen', False):
    exe_dir = os.path.dirname(sys.executable)
    db_path = os.path.join(exe_dir, 'horizonboard.db')
    upload_folder_path = os.path.join(exe_dir, 'uploads')
    app.template_folder = os.path.join(sys._MEIPASS, 'templates')
    app.static_folder = os.path.join(sys._MEIPASS, 'static')
else:
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(basedir, 'horizonboard.db')
    upload_folder_path = os.path.join(basedir, 'uploads')

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
os.makedirs(upload_folder_path, exist_ok=True)
app.config['UPLOAD_FOLDER'] = upload_folder_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('HORIZONBOARD_SECRET_KEY', 'horizonboard-dev-2024')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'log'}

db = SQLAlchemy(app)

# --- Association Table ---
projekt_kontakte = Table('projekt_kontakte', db.metadata,
    Column('projekt_id', Integer, ForeignKey('projekt.id'), primary_key=True),
    Column('kontakt_id', Integer, ForeignKey('kontakt.id'), primary_key=True)
)

# ============================================================
# MODELLE
# ============================================================

class Kontakt(db.Model):
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(150), nullable=False)
    email = db.Column(String(150), nullable=True, unique=True)
    telefon = db.Column(String(50), nullable=True)
    firma = db.Column(String(150), nullable=True)
    notizen = db.Column(Text, nullable=True)
    erstellt_am = db.Column(DateTime, default=datetime.utcnow)
    projekte = db.relationship('Projekt', secondary=projekt_kontakte, back_populates='kontakte', lazy='dynamic')
    wartende_aufgaben = db.relationship('Aufgabe', backref='wartet_auf_kontakt', lazy='dynamic',
                                        foreign_keys='Aufgabe.wartet_auf_kontakt_id')

class Projekt(db.Model):
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(100), nullable=False)
    beschreibung = db.Column(Text, nullable=True)
    kuerzel = db.Column(String(10), nullable=True, default='PROJ')
    erstellt_am = db.Column(DateTime, default=datetime.utcnow)
    erledigt_am = db.Column(DateTime, nullable=True)
    kontakte = db.relationship('Kontakt', secondary=projekt_kontakte, back_populates='projekte', lazy='dynamic')
    aufgaben = db.relationship('Aufgabe', backref='projekt_ref', lazy='dynamic',
                               cascade="all, delete-orphan", foreign_keys='Aufgabe.projekt_id')
    sprints = db.relationship('Sprint', backref='projekt', lazy='dynamic', cascade="all, delete-orphan")
    epics = db.relationship('Epic', backref='projekt', lazy='dynamic', cascade="all, delete-orphan")
    bugs = db.relationship('Bug', backref='projekt', lazy='dynamic', cascade="all, delete-orphan")
    feedbacks = db.relationship('Feedback', backref='projekt', lazy='dynamic',
                                cascade="all, delete-orphan", foreign_keys='Feedback.projekt_id')

class Sprint(db.Model):
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(100), nullable=False)
    ziel = db.Column(Text, nullable=True)
    ist_aktiv = db.Column(Boolean, default=False)
    startdatum = db.Column(DateTime, nullable=True)
    enddatum = db.Column(DateTime, nullable=True)
    projekt_id = db.Column(Integer, ForeignKey('projekt.id'), nullable=False)
    aufgaben = db.relationship('Aufgabe', backref='sprint', lazy='dynamic', foreign_keys='Aufgabe.sprint_id')
    feedbacks = db.relationship('Feedback', backref='sprint', lazy='dynamic',
                                cascade="all, delete-orphan", foreign_keys='Feedback.sprint_id')

class Epic(db.Model):
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(200), nullable=False)
    epic_nr = db.Column(String(20), nullable=True)
    phase = db.Column(String(100), default="Backlog")
    prioritaet = db.Column(String(50), default="Mittel")
    startdatum = db.Column(DateTime, nullable=True)
    enddatum = db.Column(DateTime, nullable=True)
    beschreibung = db.Column(Text, nullable=True)
    projekt_id = db.Column(Integer, ForeignKey('projekt.id'), nullable=False)
    aufgaben = db.relationship('Aufgabe', backref='epic', lazy='dynamic', foreign_keys='Aufgabe.epic_id')

class Aufgabe(db.Model):
    id = db.Column(Integer, primary_key=True)
    aufgaben_nr = db.Column(String(20), nullable=True)
    titel = db.Column(String(200), nullable=False)
    beschreibung = db.Column(Text, nullable=True)
    erstellt_am = db.Column(DateTime, default=datetime.utcnow)
    erledigt_am = db.Column(DateTime, nullable=True)
    status = db.Column(String(100), default="Startbereit")
    prioritaet = db.Column(String(50), default="Mittel")
    aufgaben_typ = db.Column(String(50), nullable=True)
    faelligkeitsdatum = db.Column(DateTime, nullable=True)
    story_points_geschaetzt = db.Column(Integer, nullable=True)
    story_points_aktuell = db.Column(Integer, nullable=True)
    ungeplant = db.Column(Boolean, default=False)
    projekt_id = db.Column(Integer, ForeignKey('projekt.id'), nullable=False)
    sprint_id = db.Column(Integer, ForeignKey('sprint.id'), nullable=True)
    epic_id = db.Column(Integer, ForeignKey('epic.id'), nullable=True)
    wartet_auf_kontakt_id = db.Column(Integer, ForeignKey('kontakt.id'), nullable=True)
    anhaenge = db.relationship('Anhang', backref='aufgabe', lazy=True, cascade="all, delete-orphan")
    protokoll_eintraege = db.relationship('ProtokollEintrag', backref='aufgabe', lazy=True,
                                          order_by='ProtokollEintrag.erstellt_am', cascade="all, delete-orphan")
    @property
    def status_klasse(self): return STATUS_KLASSEN.get(self.status, 'status-default')
    @property
    def prio_klasse(self): return PRIO_KLASSEN.get(self.prioritaet, 'prio-default')
    @property
    def typ_klasse(self): return TYP_KLASSEN.get(self.aufgaben_typ, 'typ-default')

class Anhang(db.Model):
    id = db.Column(Integer, primary_key=True)
    dateiname_original = db.Column(String(255), nullable=False)
    dateiname_sicher = db.Column(String(255), nullable=False, unique=True)
    pfad_relativ = db.Column(String(255), nullable=False)
    mime_typ = db.Column(String(100), nullable=True)
    groesse = db.Column(BigInteger, nullable=True)
    hochgeladen_am = db.Column(DateTime, default=datetime.utcnow)
    aufgabe_id = db.Column(Integer, ForeignKey('aufgabe.id'), nullable=False)

class ProtokollEintrag(db.Model):
    id = db.Column(Integer, primary_key=True)
    eintrag = db.Column(Text, nullable=False)
    erstellt_am = db.Column(DateTime, default=datetime.utcnow)
    aufgabe_id = db.Column(Integer, ForeignKey('aufgabe.id'), nullable=False)

class Bug(db.Model):
    id = db.Column(Integer, primary_key=True)
    bug_nr = db.Column(String(20), nullable=True)
    titel = db.Column(String(200), nullable=False)
    beschreibung = db.Column(Text, nullable=True)
    status = db.Column(String(100), default="Prüfung ausstehend")
    prioritaet = db.Column(String(50), default="Mittel")
    gruppe = db.Column(String(100), default="Eingehende Bugs")
    erstellt_am = db.Column(DateTime, default=datetime.utcnow)
    projekt_id = db.Column(Integer, ForeignKey('projekt.id'), nullable=False)
    gemeldet_von_id = db.Column(Integer, ForeignKey('kontakt.id'), nullable=True)
    gemeldet_von = db.relationship('Kontakt', foreign_keys=[gemeldet_von_id])
    @property
    def status_klasse(self): return BUG_STATUS_KLASSEN.get(self.status, 'status-default')
    @property
    def prio_klasse(self): return PRIO_KLASSEN.get(self.prioritaet, 'prio-default')

class Feedback(db.Model):
    id = db.Column(Integer, primary_key=True)
    inhalt = db.Column(Text, nullable=False)
    typ = db.Column(String(50), default="Diskussion")
    wiederholung = db.Column(Boolean, default=False)
    abstimmung = db.Column(Integer, default=0)
    sprint_id = db.Column(Integer, ForeignKey('sprint.id'), nullable=True)
    projekt_id = db.Column(Integer, ForeignKey('projekt.id'), nullable=False)
    @property
    def typ_klasse(self): return FEEDBACK_KLASSEN.get(self.typ, 'typ-default')

# ============================================================
# HELPERS
# ============================================================

def allowed_file(fn):
    return '.' in fn and fn.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generiere_aufgaben_nr(projekt):
    k = (projekt.kuerzel or 'TASK').upper()
    n = Aufgabe.query.filter_by(projekt_id=projekt.id).count() + 1
    return f"{k}-{n:03d}"

def generiere_epic_nr(projekt):
    k = (projekt.kuerzel or 'EPIC').upper()
    n = Epic.query.filter_by(projekt_id=projekt.id).count() + 1
    return f"E{k}-{n:03d}"

def generiere_bug_nr(projekt):
    k = (projekt.kuerzel or 'BUG').upper()
    n = Bug.query.filter_by(projekt_id=projekt.id).count() + 1
    return f"B{k}-{n:03d}"

@app.errorhandler(413)
@app.errorhandler(RequestEntityTooLarge)
def zu_grosse_datei(e):
    flash(f"Datei zu groß (Max: {app.config['MAX_CONTENT_LENGTH']//1024//1024} MB).", "error")
    return redirect(request.referrer or url_for('dashboard'))

@app.before_request
def before_request():
    g.alle_projekte = Projekt.query.order_by(Projekt.name).all()
    g.projekt_id = None
    
    # Git integration
    try:
        import subprocess
        g.git_branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], stderr=subprocess.STDOUT).decode().strip()
        print(f"Git branch found: {g.git_branch}")
    except Exception as e:
        g.git_branch = None
        print(f"Git branch error: {e}")
    if request.view_args:
        pid = request.view_args.get('projekt_id')
        if pid:
            try:
                g.projekt_id = int(pid)
            except (ValueError, TypeError):
                pass

# Jinja2 Globals
@app.context_processor
def inject_globals():
    return dict(
        AUFGABEN_STATUS=AUFGABEN_STATUS, STATUS_KLASSEN=STATUS_KLASSEN,
        PRIORITAETEN=PRIORITAETEN, PRIO_KLASSEN=PRIO_KLASSEN,
        AUFGABEN_TYPEN=AUFGABEN_TYPEN, TYP_KLASSEN=TYP_KLASSEN,
        EPIC_PHASEN=EPIC_PHASEN, BUG_GRUPPEN=BUG_GRUPPEN,
        BUG_STATUS=BUG_STATUS, BUG_STATUS_KLASSEN=BUG_STATUS_KLASSEN,
        FEEDBACK_TYPEN=FEEDBACK_TYPEN, FEEDBACK_KLASSEN=FEEDBACK_KLASSEN,
        now=datetime.utcnow()
    )

# ============================================================
# ROUTEN
# ============================================================

@app.route('/')
def dashboard():
    projekte = Projekt.query.order_by(Projekt.name).all()
    return render_template('dashboard.html', projekte=projekte)

@app.route('/projekt/neu', methods=['GET', 'POST'])
def neues_projekt():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash("Projektname fehlt.", "error")
            return redirect(url_for('neues_projekt'))
        kuerzel = request.form.get('kuerzel', name[:4]).strip().upper()
        p = Projekt(name=name, beschreibung=request.form.get('beschreibung', ''), kuerzel=kuerzel)
        try:
            db.session.add(p)
            db.session.commit()
            # Standard-Sprint erstellen
            s = Sprint(name="Sprint 1", ziel="Erster Sprint", ist_aktiv=True, projekt_id=p.id,
                       startdatum=datetime.utcnow(), enddatum=datetime.utcnow() + timedelta(days=14))
            db.session.add(s)
            db.session.commit()
            flash(f"Projekt '{name}' erstellt.", "success")
            return redirect(url_for('aufgaben_board', projekt_id=p.id))
        except Exception as e:
            db.session.rollback()
            flash(f"Fehler: {e}", "error")
    return render_template('projekt_form.html')



# --- AUFGABEN BOARD ---
@app.route('/projekt/<int:projekt_id>/aufgaben')
def aufgaben_board(projekt_id):
    projekt = Projekt.query.get_or_404(projekt_id)
    sprints = Sprint.query.filter_by(projekt_id=projekt_id).order_by(Sprint.ist_aktiv.desc(), Sprint.id).all()
    epics = Epic.query.filter_by(projekt_id=projekt_id).order_by(Epic.name).all()
    kontakte = Kontakt.query.order_by(Kontakt.name).all()
    # Aufgaben pro Sprint gruppieren
    sprint_aufgaben = {}
    for sp in sprints:
        sprint_aufgaben[sp.id] = Aufgabe.query.filter_by(sprint_id=sp.id)\
            .options(joinedload(Aufgabe.epic), joinedload(Aufgabe.wartet_auf_kontakt)).all()
    backlog_aufgaben = Aufgabe.query.filter_by(projekt_id=projekt_id, sprint_id=None)\
        .options(joinedload(Aufgabe.epic)).all()
    return render_template('aufgaben_board.html', projekt=projekt, sprints=sprints,
                           sprint_aufgaben=sprint_aufgaben, backlog_aufgaben=backlog_aufgaben,
                           epics=epics, kontakte=kontakte)

@app.route('/projekt/<int:projekt_id>/aufgaben/kanban')
def aufgaben_kanban(projekt_id):
    projekt = Projekt.query.get_or_404(projekt_id)
    aktiver_sprint = Sprint.query.filter_by(projekt_id=projekt_id, ist_aktiv=True).first()
    alle_aufgaben = Aufgabe.query.filter_by(projekt_id=projekt_id)\
        .options(joinedload(Aufgabe.epic)).all()
    if aktiver_sprint:
        aufgaben = [a for a in alle_aufgaben if a.sprint_id == aktiver_sprint.id]
    else:
        aufgaben = alle_aufgaben
    nach_status = defaultdict(list)
    for a in aufgaben:
        nach_status[a.status].append(a)
    return render_template('aufgaben_kanban.html', projekt=projekt,
                           aktiver_sprint=aktiver_sprint, nach_status=nach_status,
                           AUFGABEN_STATUS=AUFGABEN_STATUS)

# --- AUFGABE DETAIL ---
@app.route('/aufgabe/<int:aufgaben_id>/detail')
def aufgabe_detail(aufgaben_id):
    a = Aufgabe.query.options(
        joinedload(Aufgabe.sprint), joinedload(Aufgabe.epic),
        joinedload(Aufgabe.wartet_auf_kontakt), joinedload(Aufgabe.anhaenge),
        joinedload(Aufgabe.protokoll_eintraege)
    ).get_or_404(aufgaben_id)
    projekt = Projekt.query.get_or_404(a.projekt_id)
    sprints = Sprint.query.filter_by(projekt_id=a.projekt_id).all()
    epics = Epic.query.filter_by(projekt_id=a.projekt_id).all()
    kontakte = Kontakt.query.order_by(Kontakt.name).all()
    return render_template('aufgabe_detail.html', aufgabe=a, projekt=projekt,
                           sprints=sprints, epics=epics, kontakte=kontakte)

# --- AUFGABE ERSTELLEN ---
@app.route('/aufgabe/erstellen', methods=['POST'])
def aufgabe_erstellen():
    projekt_id = request.form.get('projekt_id', type=int)
    titel = request.form.get('titel', '').strip()
    if not projekt_id or not titel:
        flash("Projekt-ID und Titel erforderlich.", "error")
        return redirect(url_for('dashboard'))
    projekt = Projekt.query.get_or_404(projekt_id)
    sprint_id = request.form.get('sprint_id', type=int)
    epic_id = request.form.get('epic_id', type=int) or None
    status = request.form.get('status', 'Startbereit')
    prioritaet = request.form.get('prioritaet', 'Mittel')
    aufgaben_typ = request.form.get('aufgaben_typ') or None
    spe = request.form.get('story_points_geschaetzt', type=int)
    fdate = request.form.get('faelligkeitsdatum')
    faellig = None
    if fdate:
        try:
            faellig = datetime.strptime(fdate, '%Y-%m-%d')
        except ValueError:
            pass
    a = Aufgabe(
        titel=titel, projekt_id=projekt_id, sprint_id=sprint_id, epic_id=epic_id,
        status=status, prioritaet=prioritaet, aufgaben_typ=aufgaben_typ,
        story_points_geschaetzt=spe, faelligkeitsdatum=faellig,
        beschreibung=request.form.get('beschreibung', ''),
        ungeplant=bool(request.form.get('ungeplant'))
    )
    a.aufgaben_nr = generiere_aufgaben_nr(projekt)
    if status == 'Erledigt':
        a.erledigt_am = datetime.utcnow()
    try:
        db.session.add(a)
        db.session.commit()
        flash(f"Aufgabe '{titel}' erstellt.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Fehler: {e}", "error")
    return redirect(request.form.get('next_url') or url_for('aufgaben_board', projekt_id=projekt_id))

# --- AUFGABE AKTUALISIEREN (Formular) ---
@app.route('/aufgabe/<int:aufgaben_id>/aktualisieren', methods=['POST'])
def aufgabe_aktualisieren(aufgaben_id):
    a = Aufgabe.query.get_or_404(aufgaben_id)
    a.titel = request.form.get('titel', a.titel).strip() or a.titel
    a.beschreibung = request.form.get('beschreibung', '')
    a.status = request.form.get('status', a.status)
    a.prioritaet = request.form.get('prioritaet', a.prioritaet)
    a.aufgaben_typ = request.form.get('aufgaben_typ') or None
    a.sprint_id = request.form.get('sprint_id', type=int) or None
    a.epic_id = request.form.get('epic_id', type=int) or None
    a.story_points_geschaetzt = request.form.get('story_points_geschaetzt', type=int)
    a.story_points_aktuell = request.form.get('story_points_aktuell', type=int)
    a.ungeplant = bool(request.form.get('ungeplant'))
    if a.status == 'Erledigt' and not a.erledigt_am:
        a.erledigt_am = datetime.utcnow()
    elif a.status != 'Erledigt':
        a.erledigt_am = None
    fdate = request.form.get('faelligkeitsdatum')
    if fdate:
        try:
            a.faelligkeitsdatum = datetime.strptime(fdate, '%Y-%m-%d')
        except ValueError:
            pass
    else:
        a.faelligkeitsdatum = None
    try:
        db.session.commit()
        flash(f"Aufgabe '{a.titel}' aktualisiert.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Fehler: {e}", "error")
    return redirect(url_for('aufgabe_detail', aufgaben_id=aufgaben_id))

# --- AUFGABE INLINE-UPDATE API ---
@app.route('/api/aufgabe/<int:aufgaben_id>', methods=['PATCH'])
def api_aufgabe_update(aufgaben_id):
    a = Aufgabe.query.get_or_404(aufgaben_id)
    data = request.get_json()
    if not data:
        return jsonify({"error": "Kein JSON"}), 400
    erlaubte_felder = {'status', 'prioritaet', 'aufgaben_typ', 'sprint_id', 'epic_id',
                       'story_points_geschaetzt', 'story_points_aktuell', 'ungeplant', 'titel'}
    for feld, wert in data.items():
        if feld in erlaubte_felder:
            setattr(a, feld, wert)
    if a.status == 'Erledigt' and not a.erledigt_am:
        a.erledigt_am = datetime.utcnow()
    elif a.status != 'Erledigt':
        a.erledigt_am = None
    try:
        db.session.commit()
        return jsonify({"success": True, "status_klasse": a.status_klasse,
                        "prio_klasse": a.prio_klasse, "typ_klasse": a.typ_klasse}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# --- AUFGABE LOESCHEN ---
@app.route('/aufgabe/<int:aufgaben_id>/loeschen', methods=['POST'])
def aufgabe_loeschen(aufgaben_id):
    a = Aufgabe.query.get_or_404(aufgaben_id)
    projekt_id = a.projekt_id
    titel = a.titel
    # Anhänge von Disk löschen
    for anh in a.anhaenge:
        fp = os.path.join(app.config['UPLOAD_FOLDER'], anh.pfad_relativ, anh.dateiname_sicher)
        if os.path.exists(fp):
            try:
                os.remove(fp)
            except OSError:
                pass
    try:
        db.session.delete(a)
        db.session.commit()
        flash(f"Aufgabe '{titel}' gelöscht.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Fehler: {e}", "error")
    return redirect(request.form.get('next_url') or url_for('aufgaben_board', projekt_id=projekt_id))

# --- PROTOKOLL ---
@app.route('/aufgabe/<int:aufgaben_id>/protokoll', methods=['POST'])
def protokoll_hinzufuegen(aufgaben_id):
    a = Aufgabe.query.get_or_404(aufgaben_id)
    text = request.form.get('protokoll_text', '').strip()
    if text:
        try:
            db.session.add(ProtokollEintrag(eintrag=text, aufgabe_id=aufgaben_id))
            db.session.commit()
            flash("Eintrag hinzugefügt.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Fehler: {e}", "error")
    return redirect(url_for('aufgabe_detail', aufgaben_id=aufgaben_id))

# --- ANHANG ---
@app.route('/aufgabe/<int:aufgaben_id>/anhang', methods=['POST'])
def anhang_hochladen(aufgaben_id):
    a = Aufgabe.query.get_or_404(aufgaben_id)
    if 'datei' not in request.files:
        flash("Keine Datei.", "error")
        return redirect(url_for('aufgabe_detail', aufgaben_id=aufgaben_id))
    file = request.files['datei']
    if file.filename == '' or not allowed_file(file.filename):
        flash("Kein gültiger Dateityp.", "warning")
        return redirect(url_for('aufgabe_detail', aufgaben_id=aufgaben_id))
    orig = secure_filename(file.filename)
    ext = orig.rsplit('.', 1)[1].lower() if '.' in orig else ''
    sname = f"{uuid.uuid4()}.{ext}"
    relpath = os.path.join('task_files', str(aufgaben_id))
    abspath = os.path.join(app.config['UPLOAD_FOLDER'], relpath)
    os.makedirs(abspath, exist_ok=True)
    fpath = os.path.join(abspath, sname)
    try:
        file.save(fpath)
        anh = Anhang(dateiname_original=orig, dateiname_sicher=sname,
                     pfad_relativ=relpath, mime_typ=file.mimetype,
                     groesse=os.path.getsize(fpath), aufgabe_id=aufgaben_id)
        db.session.add(anh)
        db.session.commit()
        flash(f"'{orig}' hochgeladen.", "success")
    except Exception as e:
        db.session.rollback()
        if os.path.exists(fpath):
            os.remove(fpath)
        flash(f"Fehler: {e}", "error")
    return redirect(url_for('aufgabe_detail', aufgaben_id=aufgaben_id))

@app.route('/anhang/<int:anhang_id>/download')
def anhang_download(anhang_id):
    anh = Anhang.query.get_or_404(anhang_id)
    directory = os.path.join(app.config['UPLOAD_FOLDER'], anh.pfad_relativ)
    try:
        return send_from_directory(directory, anh.dateiname_sicher,
                                   as_attachment=True, download_name=anh.dateiname_original)
    except FileNotFoundError:
        flash("Datei nicht gefunden.", "error")
        return redirect(url_for('dashboard'))

# --- SPRINTS ---
@app.route('/projekt/<int:projekt_id>/sprints')
def sprints_liste(projekt_id):
    projekt = Projekt.query.get_or_404(projekt_id)
    sprints = Sprint.query.filter_by(projekt_id=projekt_id).order_by(Sprint.ist_aktiv.desc(), Sprint.id).all()
    return render_template('sprints.html', projekt=projekt, sprints=sprints)

@app.route('/projekt/<int:projekt_id>/sprint/erstellen', methods=['POST'])
def sprint_erstellen(projekt_id):
    projekt = Projekt.query.get_or_404(projekt_id)
    name = request.form.get('name', '').strip()
    if not name:
        flash("Sprint-Name erforderlich.", "error")
        return redirect(url_for('sprints_liste', projekt_id=projekt_id))
    sdate = request.form.get('startdatum')
    edate = request.form.get('enddatum')
    s = Sprint(name=name, ziel=request.form.get('ziel', ''),
               projekt_id=projekt_id,
               startdatum=datetime.strptime(sdate, '%Y-%m-%d') if sdate else None,
               enddatum=datetime.strptime(edate, '%Y-%m-%d') if edate else None)
    try:
        db.session.add(s)
        db.session.commit()
        flash(f"Sprint '{name}' erstellt.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Fehler: {e}", "error")
    return redirect(url_for('sprints_liste', projekt_id=projekt_id))

@app.route('/projekt/<int:projekt_id>/sprint/<int:sprint_id>/aktivieren', methods=['POST'])
def sprint_aktivieren(projekt_id, sprint_id):
    # Alle anderen deaktivieren
    Sprint.query.filter_by(projekt_id=projekt_id).update({'ist_aktiv': False})
    s = Sprint.query.get_or_404(sprint_id)
    s.ist_aktiv = True
    try:
        db.session.commit()
        flash(f"Sprint '{s.name}' aktiviert.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Fehler: {e}", "error")
    return redirect(url_for('sprints_liste', projekt_id=projekt_id))

@app.route('/projekt/<int:projekt_id>/sprint/<int:sprint_id>/loeschen', methods=['POST'])
def sprint_loeschen(projekt_id, sprint_id):
    s = Sprint.query.get_or_404(sprint_id)
    name = s.name
    # Aufgaben in Backlog verschieben
    Aufgabe.query.filter_by(sprint_id=sprint_id).update({'sprint_id': None})
    try:
        db.session.delete(s)
        db.session.commit()
        flash(f"Sprint '{name}' gelöscht.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Fehler: {e}", "error")
    return redirect(url_for('sprints_liste', projekt_id=projekt_id))

# --- EPICS ---
@app.route('/projekt/<int:projekt_id>/epics')
def epics_liste(projekt_id):
    projekt = Projekt.query.get_or_404(projekt_id)
    epics = Epic.query.filter_by(projekt_id=projekt_id).order_by(Epic.prioritaet, Epic.name).all()
    sprints = Sprint.query.filter_by(projekt_id=projekt_id).all()
    return render_template('epics.html', projekt=projekt, epics=epics, sprints=sprints)

@app.route('/projekt/<int:projekt_id>/epic/erstellen', methods=['POST'])
def epic_erstellen(projekt_id):
    projekt = Projekt.query.get_or_404(projekt_id)
    name = request.form.get('name', '').strip()
    if not name:
        flash("Epic-Name erforderlich.", "error")
        return redirect(url_for('epics_liste', projekt_id=projekt_id))
    sdate = request.form.get('startdatum')
    edate = request.form.get('enddatum')
    e = Epic(name=name, projekt_id=projekt_id,
             phase=request.form.get('phase', 'Backlog'),
             prioritaet=request.form.get('prioritaet', 'Mittel'),
             beschreibung=request.form.get('beschreibung', ''),
             startdatum=datetime.strptime(sdate, '%Y-%m-%d') if sdate else None,
             enddatum=datetime.strptime(edate, '%Y-%m-%d') if edate else None)
    e.epic_nr = generiere_epic_nr(projekt)
    try:
        db.session.add(e)
        db.session.commit()
        flash(f"Epic '{name}' erstellt.", "success")
    except Exception as e_err:
        db.session.rollback()
        flash(f"Fehler: {e_err}", "error")
    return redirect(url_for('epics_liste', projekt_id=projekt_id))

@app.route('/api/epic/<int:epic_id>', methods=['PATCH'])
def api_epic_update(epic_id):
    e = Epic.query.get_or_404(epic_id)
    data = request.get_json() or {}
    for feld in {'phase', 'prioritaet', 'name'}:
        if feld in data:
            setattr(e, feld, data[feld])
    try:
        db.session.commit()
        return jsonify({"success": True,
                        "prio_klasse": PRIO_KLASSEN.get(e.prioritaet, '')}), 200
    except Exception as ex:
        db.session.rollback()
        return jsonify({"error": str(ex)}), 500

@app.route('/projekt/<int:projekt_id>/epic/<int:epic_id>/loeschen', methods=['POST'])
def epic_loeschen(projekt_id, epic_id):
    e = Epic.query.get_or_404(epic_id)
    name = e.name
    Aufgabe.query.filter_by(epic_id=epic_id).update({'epic_id': None})
    try:
        db.session.delete(e)
        db.session.commit()
        flash(f"Epic '{name}' gelöscht.", "success")
    except Exception as ex:
        db.session.rollback()
        flash(f"Fehler: {ex}", "error")
    return redirect(url_for('epics_liste', projekt_id=projekt_id))

# --- BUGS ---
@app.route('/projekt/<int:projekt_id>/bugs')
def bugs_liste(projekt_id):
    projekt = Projekt.query.get_or_404(projekt_id)
    bugs = Bug.query.filter_by(projekt_id=projekt_id).options(
        joinedload(Bug.gemeldet_von)
    ).order_by(Bug.gruppe, Bug.erstellt_am.desc()).all()
    nach_gruppe = defaultdict(list)
    for b in bugs:
        nach_gruppe[b.gruppe].append(b)
    kontakte = Kontakt.query.order_by(Kontakt.name).all()
    return render_template('bugs.html', projekt=projekt, nach_gruppe=nach_gruppe,
                           BUG_GRUPPEN=BUG_GRUPPEN, kontakte=kontakte)

@app.route('/projekt/<int:projekt_id>/bug/erstellen', methods=['POST'])
def bug_erstellen(projekt_id):
    projekt = Projekt.query.get_or_404(projekt_id)
    titel = request.form.get('titel', '').strip()
    if not titel:
        flash("Bug-Titel erforderlich.", "error")
        return redirect(url_for('bugs_liste', projekt_id=projekt_id))
    b = Bug(titel=titel, projekt_id=projekt_id,
            status=request.form.get('status', 'Prüfung ausstehend'),
            prioritaet=request.form.get('prioritaet', 'Mittel'),
            gruppe=request.form.get('gruppe', 'Eingehende Bugs'),
            beschreibung=request.form.get('beschreibung', ''),
            gemeldet_von_id=request.form.get('gemeldet_von_id', type=int) or None)
    b.bug_nr = generiere_bug_nr(projekt)
    try:
        db.session.add(b)
        db.session.commit()
        flash(f"Bug '{titel}' gemeldet.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Fehler: {e}", "error")
    return redirect(url_for('bugs_liste', projekt_id=projekt_id))

@app.route('/api/bug/<int:bug_id>', methods=['PATCH'])
def api_bug_update(bug_id):
    b = Bug.query.get_or_404(bug_id)
    data = request.get_json() or {}
    for feld in {'status', 'prioritaet', 'gruppe', 'titel'}:
        if feld in data:
            setattr(b, feld, data[feld])
    try:
        db.session.commit()
        return jsonify({"success": True, "status_klasse": b.status_klasse,
                        "prio_klasse": b.prio_klasse}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/projekt/<int:projekt_id>/bug/<int:bug_id>/loeschen', methods=['POST'])
def bug_loeschen(projekt_id, bug_id):
    b = Bug.query.get_or_404(bug_id)
    titel = b.titel
    try:
        db.session.delete(b)
        db.session.commit()
        flash(f"Bug '{titel}' gelöscht.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Fehler: {e}", "error")
    return redirect(url_for('bugs_liste', projekt_id=projekt_id))

# --- RETROSPEKTIVE ---
@app.route('/projekt/<int:projekt_id>/retrospektive')
def retrospektive(projekt_id):
    projekt = Projekt.query.get_or_404(projekt_id)
    sprints = Sprint.query.filter_by(projekt_id=projekt_id).order_by(Sprint.id.desc()).all()
    sprint_id_filter = request.args.get('sprint_id', type=int)
    if sprint_id_filter:
        feedbacks = Feedback.query.filter_by(projekt_id=projekt_id, sprint_id=sprint_id_filter).all()
        aktiver_sprint = Sprint.query.get(sprint_id_filter)
    else:
        aktiver_sprint = Sprint.query.filter_by(projekt_id=projekt_id, ist_aktiv=True).first()
        feedbacks = Feedback.query.filter_by(
            projekt_id=projekt_id,
            sprint_id=aktiver_sprint.id if aktiver_sprint else None
        ).all()
    return render_template('retrospektive.html', projekt=projekt, sprints=sprints,
                           feedbacks=feedbacks, aktiver_sprint=aktiver_sprint)

@app.route('/projekt/<int:projekt_id>/feedback/erstellen', methods=['POST'])
def feedback_erstellen(projekt_id):
    inhalt = request.form.get('inhalt', '').strip()
    if not inhalt:
        flash("Feedback-Inhalt fehlt.", "error")
        return redirect(url_for('retrospektive', projekt_id=projekt_id))
    sprint_id = request.form.get('sprint_id', type=int) or None
    f = Feedback(inhalt=inhalt, projekt_id=projekt_id, sprint_id=sprint_id,
                 typ=request.form.get('typ', 'Diskussion'),
                 wiederholung=bool(request.form.get('wiederholung')))
    try:
        db.session.add(f)
        db.session.commit()
        flash("Feedback hinzugefügt.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Fehler: {e}", "error")
    return redirect(url_for('retrospektive', projekt_id=projekt_id,
                            sprint_id=sprint_id) if sprint_id else url_for('retrospektive', projekt_id=projekt_id))

@app.route('/feedback/<int:feedback_id>/abstimmen', methods=['POST'])
def feedback_abstimmen(feedback_id):
    f = Feedback.query.get_or_404(feedback_id)
    f.abstimmung = (f.abstimmung or 0) + 1
    try:
        db.session.commit()
        return jsonify({"success": True, "abstimmung": f.abstimmung}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/feedback/<int:feedback_id>/loeschen', methods=['POST'])
def feedback_loeschen(feedback_id):
    f = Feedback.query.get_or_404(feedback_id)
    p_id = f.projekt_id
    try:
        db.session.delete(f)
        db.session.commit()
        flash("Feedback gelöscht.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Fehler: {e}", "error")
    return redirect(url_for('retrospektive', projekt_id=p_id))

# --- KONTAKTE ---
@app.route('/kontakte')
def kontakte_liste():
    return render_template('kontakte.html', kontakte=Kontakt.query.order_by(Kontakt.name).all())

@app.route('/kontakt/neu', methods=['GET', 'POST'])
def neuer_kontakt():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash("Name erforderlich.", "error")
            return redirect(url_for('neuer_kontakt'))
        k = Kontakt(name=name, email=request.form.get('email'),
                    telefon=request.form.get('telefon'), firma=request.form.get('firma'),
                    notizen=request.form.get('notizen'))
        try:
            db.session.add(k)
            db.session.commit()
            flash(f"Kontakt '{name}' erstellt.", "success")
            return redirect(url_for('kontakte_liste'))
        except Exception as e:
            db.session.rollback()
            flash(f"Fehler: {e}", "error")
    return render_template('kontakt_form.html')

@app.route('/kontakt/<int:kontakt_id>/bearbeiten', methods=['GET', 'POST'])
def kontakt_bearbeiten(kontakt_id):
    k = Kontakt.query.get_or_404(kontakt_id)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash("Name erforderlich.", "error")
            return redirect(url_for('kontakt_bearbeiten', kontakt_id=kontakt_id))
        k.name = name
        k.email = request.form.get('email')
        k.telefon = request.form.get('telefon')
        k.firma = request.form.get('firma')
        k.notizen = request.form.get('notizen')
        try:
            db.session.commit()
            flash(f"Kontakt aktualisiert.", "success")
            return redirect(url_for('kontakte_liste'))
        except Exception as e:
            db.session.rollback()
            flash(f"Fehler: {e}", "error")
    return render_template('kontakt_form.html', kontakt=k)

@app.route('/kontakt/<int:kontakt_id>/loeschen', methods=['POST'])
def kontakt_loeschen(kontakt_id):
    k = Kontakt.query.get_or_404(kontakt_id)
    name = k.name
    try:
        db.session.delete(k)
        db.session.commit()
        flash(f"Kontakt '{name}' gelöscht.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Fehler: {e}", "error")
    return redirect(url_for('kontakte_liste'))

# --- PROJEKT LOESCHEN ---
@app.route('/projekt/<int:projekt_id>/loeschen', methods=['POST'])
def projekt_loeschen(projekt_id):
    p = Projekt.query.get_or_404(projekt_id)
    name = p.name
    try:
        # Alle verknüpften Daten löschen (Cascade)
        for a in p.aufgaben.all():
            for anh in a.anhaenge:
                fp = os.path.join(app.config['UPLOAD_FOLDER'],
                                  anh.pfad_relativ, anh.dateiname_sicher)
                if os.path.exists(fp):
                    try: os.remove(fp)
                    except OSError: pass
        db.session.delete(p)
        db.session.commit()
        flash(f"Projekt '{name}' und alle zugehörigen Daten wurden gelöscht.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Fehler beim Löschen: {e}", "error")
    return redirect(url_for('dashboard'))


# DB INIT
# ============================================================
def init_db():
    with app.app_context():
        db.create_all()
        print("Datenbanktabellen bereit.")
        if not Projekt.query.first():
            print("Erstelle Beispieldaten...")
            try:
                # Kontakte
                k1 = Kontakt(name="Anna Müller", email="anna@example.com", firma="Dev GmbH")
                k2 = Kontakt(name="Ben Bauer", email="ben@example.com", telefon="0123 456")
                db.session.add_all([k1, k2])
                db.session.flush()

                # Projekt
                p = Projekt(name="Mein Team", kuerzel="THIT",
                            beschreibung="Hauptprojekt für unser Team")
                db.session.add(p)
                db.session.flush()

                # Sprints
                s1 = Sprint(name="Sprint 1", ziel="MVP-Features fertigstellen",
                            ist_aktiv=True, projekt_id=p.id,
                            startdatum=datetime.utcnow() - timedelta(days=7),
                            enddatum=datetime.utcnow() + timedelta(days=7))
                db.session.add(s1)
                db.session.flush()

                # Epics
                e1 = Epic(name="Infrastruktur", epic_nr="ETHIT-001", phase="Dev in Arbeit",
                          prioritaet="Hoch", projekt_id=p.id,
                          startdatum=datetime.utcnow(),
                          enddatum=datetime.utcnow() + timedelta(days=30))
                e2 = Epic(name="Datenbankpflege", epic_nr="ETHIT-002", phase="Produkt Discovery",
                          prioritaet="Kritisch", projekt_id=p.id)
                db.session.add_all([e1, e2])
                db.session.flush()

                # Aufgaben
                a1 = Aufgabe(aufgaben_nr="THIT-001", titel="Aufgabe 1",
                             projekt_id=p.id, sprint_id=s1.id, epic_id=e1.id,
                             status="In Bearbeitung", prioritaet="Hoch",
                             aufgaben_typ="Funktion", story_points_geschaetzt=3)
                a2 = Aufgabe(aufgaben_nr="THIT-002", titel="Aufgabe 2",
                             projekt_id=p.id, sprint_id=s1.id,
                             status="Startbereit", prioritaet="Mittel",
                             aufgaben_typ="Fehler", story_points_geschaetzt=2)
                a3 = Aufgabe(aufgaben_nr="THIT-003", titel="Backlog Aufgabe",
                             projekt_id=p.id, sprint_id=None,
                             status="Startbereit", prioritaet="Niedrig")
                db.session.add_all([a1, a2, a3])
                db.session.flush()

                # Protokoll
                db.session.add(ProtokollEintrag(
                    eintrag="Aufgabe begonnen.", aufgabe_id=a1.id,
                    erstellt_am=datetime.utcnow() - timedelta(hours=2)))

                # Bugs
                b1 = Bug(bug_nr="BTHIT-001", titel="Login schlägt fehl", projekt_id=p.id,
                         status="Prüfung ausstehend", prioritaet="Kritisch",
                         gruppe="Eingehende Bugs", gemeldet_von_id=k1.id)
                b2 = Bug(bug_nr="BTHIT-002", titel="Langsame Seitenladung", projekt_id=p.id,
                         status="In Bearbeitung", prioritaet="Hoch",
                         gruppe="Entwicklungsarbeiten")
                b3 = Bug(bug_nr="BTHIT-003", titel="Alter Layout-Fehler", projekt_id=p.id,
                         status="Behoben", prioritaet="Niedrig", gruppe="Behoben")
                db.session.add_all([b1, b2, b3])
                db.session.flush()

                # Feedback
                f1 = Feedback(inhalt="Gute Kommunikation im Team", typ="Behalten",
                              sprint_id=s1.id, projekt_id=p.id, abstimmung=3)
                f2 = Feedback(inhalt="Tägliche Stand-ups optimieren", typ="Verbessern",
                              sprint_id=s1.id, projekt_id=p.id, abstimmung=1)
                f3 = Feedback(inhalt="Technische Schulden adressieren", typ="Aktion",
                              sprint_id=s1.id, projekt_id=p.id, abstimmung=2)
                db.session.add_all([f1, f2, f3])

                db.session.commit()
                print("Beispieldaten erfolgreich erstellt.")
            except Exception as e:
                db.session.rollback()
                print(f"Fehler beim Erstellen der Beispieldaten: {e}")

# ============================================================
# MAIN
# ============================================================
if __name__ == '__main__':
    host, port = '127.0.0.1', 5000
    url = f"http://{host}:{port}"
    init_db()

    def run_server():
        try:
            app.run(host=host, port=port, debug=False, use_reloader=False)
        except OSError as e:
            print(f"Port {port} belegt: {e}")

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    print(f"Server läuft auf {url}")

    if getattr(sys, 'frozen', False):
        time.sleep(1.5)
        webbrowser.open_new(url)
    else:
        print(f"Öffne manuell: {url}")

    try:
        while server_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("Beendet.")