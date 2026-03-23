// Warte, bis das HTML-Dokument vollständig geladen ist
document.addEventListener('DOMContentLoaded', function () {
    // ACHTUNG: Dieses Skript ist für eine einfache Spaltenstruktur ausgelegt.
    // Das Verschieben zwischen verschiedenen Wochen-Swimlanes wird
    // wahrscheinlich NICHT korrekt funktionieren und muss ggf. angepasst werden!
    // Es sollte aber das Verschieben INNERHALB einer Woche ermöglichen.

    const columns = document.querySelectorAll('.kanban-cards');

    if (columns.length === 0) {
        console.log("Keine Kanban-Spalten (.kanban-cards) gefunden.");
        return;
    }

    console.log(`Initialisiere SortableJS für ${columns.length} Spaltenbereiche.`);

    columns.forEach(column => {
        new Sortable(column, {
            group: 'kanban', // Gruppe muss für alle Spalten gleich sein
            animation: 150,
            ghostClass: 'sortable-ghost',
            chosenClass: 'sortable-chosen',
            dragClass: 'sortable-drag',

            onEnd: function (evt) {
                const itemEl = evt.item;
                const targetColumn = evt.to; // Das .kanban-cards div der Zielspalte
                const sourceColumn = evt.from;// Das .kanban-cards div der Quellspalte

                // Prüfe, ob sich die Spalte geändert hat (innerhalb derselben Woche)
                // Diese Prüfung ist bei Swimlanes evtl. nicht mehr ausreichend!
                if (targetColumn === sourceColumn) {
                    console.log("Karte in derselben Spalte abgelegt.");
                    return;
                }

                // Hole die Aufgaben-ID und die NEUE SPALTEN-ID
                const taskId = itemEl.dataset.taskId;
                const newSpalteId = targetColumn.dataset.spalteId; // <- Holt die Spalten-ID

                if (!taskId || !newSpalteId) {
                    console.error("Fehler: Task-ID oder neue Spalten-ID konnte nicht ermittelt werden.", itemEl, targetColumn);
                    alert("Fehler beim Verschieben der Karte. Datenattribute fehlen.");
                    sourceColumn.appendChild(itemEl);
                    return;
                }

                // TODO: Hier müsste bei Swimlanes auch die Ziel-WOCHE ermittelt werden,
                // falls das Backend dies verarbeiten soll. Aktuell wird nur die Spalte geändert.

                console.log(`Verschiebe Task ID: ${taskId} in Spalte ID: ${newSpalteId}`);

                fetch(`/aufgabe/update_spalte/${taskId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ spalte_id: newSpalteId }) // Sende Spalten-ID
                })
                .then(response => {
                    if (!response.ok) {
                        return response.json().then(err => { throw new Error(err.error || `Serverfehler: ${response.status}`) });
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.success) {
                        console.log(`Spalte für Task ${taskId} erfolgreich auf ${data.new_spalte_id} aktualisiert.`);
                        itemEl.style.transition = 'background-color 0.5s ease';
                        itemEl.style.backgroundColor = '#d4edda';
                        setTimeout(() => { itemEl.style.backgroundColor = ''; }, 1000);
                        updateTaskCounts(sourceColumn, targetColumn); // Zähler aktualisieren
                    } else {
                        throw new Error(data.error || "Unbekannter Serverfehler bei Erfolgsantwort.");
                    }
                })
                .catch(error => {
                    console.error('Fehler beim Aktualisieren der Task-Spalte:', error);
                    alert(`Fehler beim Speichern der neuen Spalte: ${error.message}`);
                    sourceColumn.appendChild(itemEl); // Zurückverschieben bei Fehler
                     itemEl.style.transition = 'background-color 0.5s ease';
                     itemEl.style.backgroundColor = '#f8d7da';
                     setTimeout(() => { itemEl.style.backgroundColor = ''; }, 1500);
                });
            }
        });
    }); // Ende forEach(column => ...)

    function updateTaskCounts(sourceColEl, targetColEl) {
        // Findet den Elter (die Spalte) und dann den Titel davor
         const findAndUpdateCount = (colEl) => {
            if (!colEl) return;
            // Gehe vom .kanban-cards div zum .kanban-column div
            const columnDiv = colEl.closest('.kanban-column');
            if (!columnDiv) return;
            const titleEl = columnDiv.querySelector('.kanban-column-title'); // Finde den Titel *innerhalb* der Spalte
             if (titleEl) {
                const countSpan = titleEl.querySelector('.task-count');
                if (countSpan) {
                    countSpan.textContent = `(${colEl.children.length})`;
                 }
             }
        };
        findAndUpdateCount(sourceColEl);
        findAndUpdateCount(targetColEl);
    }

}); // Ende DOMContentLoaded