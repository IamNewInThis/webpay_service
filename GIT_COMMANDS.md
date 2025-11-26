# 📚 Guía Completa de Comandos Git

Guía rápida de los comandos Git más importantes para trabajar desde la terminal en Linux.

---

## 📊 Estado y Cambios

### Ver estado actual
```bash
git status                    # Ver archivos modificados/staged
git status -s                 # Versión corta
```

### Ver diferencias
```bash
git diff                      # Cambios no staged
git diff --staged             # Cambios en staging
git diff archivo.txt          # Diferencias en archivo específico
git diff HEAD~1               # Comparar con commit anterior
```

### Ver historial
```bash
git log                       # Historial completo
git log --oneline             # Una línea por commit
git log --oneline -5          # Últimos 5 commits
git log --graph --all         # Con gráfico de ramas
git log --author="Nombre"     # Commits de un autor
git log --since="2 weeks ago" # Desde hace 2 semanas
```

---

## ➕ Agregar y Confirmar Cambios

### Agregar archivos al staging area
```bash
git add archivo.txt           # Agregar archivo específico
git add .                     # Agregar todos los archivos
git add *.py                  # Agregar todos los .py
git add src/                  # Agregar carpeta completa
```

### Quitar archivos del staging
```bash
git restore --staged archivo.txt
git restore --staged .        # Quitar todos
```

### Hacer commit
```bash
git commit -m "Mensaje descriptivo"
git commit -am "Mensaje"      # Add + commit (solo archivos tracked)
git commit --amend            # Modificar último commit
git commit --amend -m "Nuevo mensaje"  # Cambiar mensaje del último commit
```

---

## 🔄 Deshacer Cambios

### Descartar cambios no commiteados
```bash
git restore archivo.txt       # Descartar cambios en archivo
git restore .                 # Descartar todos los cambios
git checkout -- archivo.txt   # Forma antigua
```

### Deshacer commits (3 formas)

#### 1. Soft reset (mantiene cambios en staging)
```bash
git reset --soft HEAD~1       # Deshace último commit
git reset --soft HEAD~3       # Deshace últimos 3 commits
```

#### 2. Mixed reset (mantiene cambios sin staging) - DEFAULT
```bash
git reset HEAD~1              # Deshace commit, cambios quedan sin staged
git reset HEAD~1 archivo.txt  # Reset de archivo específico
```

#### 3. Hard reset (ELIMINA TODO - PELIGROSO)
```bash
git reset --hard HEAD~1       # Elimina commit y cambios
git reset --hard origin/main  # Volver al estado remoto
```

### Revertir un commit (crea nuevo commit)
```bash
git revert abc1234            # Revierte commit específico
git revert HEAD               # Revierte último commit
```

---

## 🌿 Ramas (Branches)

### Listar ramas
```bash
git branch                    # Ramas locales
git branch -a                 # Todas las ramas (locales + remotas)
git branch -r                 # Solo ramas remotas
```

### Crear y cambiar ramas
```bash
git branch nueva-rama         # Crear rama
git checkout nueva-rama       # Cambiar a rama
git checkout -b nueva-rama    # Crear y cambiar (shortcut)
git switch nueva-rama         # Cambiar rama (comando nuevo)
git switch -c nueva-rama      # Crear y cambiar (nuevo)
```

### Renombrar rama
```bash
git branch -m nuevo-nombre    # Renombrar rama actual
git branch -m viejo nuevo     # Renombrar otra rama
```

### Eliminar ramas
```bash
git branch -d nombre-rama     # Eliminar rama (seguro)
git branch -D nombre-rama     # Forzar eliminación
git push origin --delete rama # Eliminar rama remota
```

---

## 🔀 Fusionar y Rebase

### Fusionar ramas (merge)
```bash
git checkout main             # Ir a rama destino
git merge feature             # Fusionar feature en main
git merge --no-ff feature     # Merge sin fast-forward
```

### Abortar merge con conflictos
```bash
git merge --abort
```

### Rebase (reescribir historial)
```bash
git checkout feature
git rebase main               # Rebasar feature sobre main
git rebase --continue         # Continuar después de resolver conflictos
git rebase --abort            # Abortar rebase
```

---

## ⬆️⬇️ Sincronizar con Remoto

### Descargar cambios (fetch)
```bash
git fetch origin              # Descargar sin fusionar
git fetch --all               # Descargar de todos los remotos
```

### Descargar y fusionar (pull)
```bash
git pull                      # Fetch + merge
git pull origin main          # Pull de rama específica
git pull --rebase             # Pull con rebase en lugar de merge
```

### Subir cambios (push)
```bash
git push                      # Push a rama tracking
git push origin main          # Push a rama específica
git push -u origin main       # Push y establecer tracking
git push --force              # PELIGROSO: forzar push
git push --force-with-lease   # Forzar con protección
```

### Establecer rama upstream
```bash
git push -u origin main
git branch --set-upstream-to=origin/main main
```

---

## 🏷️ Tags (Etiquetas)

### Crear tags
```bash
git tag v1.0.0                # Tag ligero
git tag -a v1.0.0 -m "Versión 1.0.0"  # Tag anotado
git tag -a v1.0.0 abc1234     # Tag en commit específico
```

### Listar y ver tags
```bash
git tag                       # Listar tags
git tag -l "v1.*"            # Filtrar tags
git show v1.0.0              # Ver detalles de tag
```

### Push tags
```bash
git push origin v1.0.0        # Push tag específico
git push origin --tags        # Push todos los tags
```

### Eliminar tags
```bash
git tag -d v1.0.0            # Eliminar local
git push origin --delete v1.0.0  # Eliminar remoto
```

---

## 🗃️ Stash (Guardar temporalmente)

### Guardar cambios temporalmente
```bash
git stash                     # Guardar cambios
git stash save "mensaje"      # Guardar con mensaje
git stash -u                  # Incluir archivos untracked
```

### Ver y aplicar stashes
```bash
git stash list                # Listar stashes
git stash show                # Ver cambios del último stash
git stash show -p             # Ver diff completo
git stash apply               # Aplicar último stash (mantiene en lista)
git stash pop                 # Aplicar y eliminar de lista
git stash apply stash@{2}     # Aplicar stash específico
```

### Eliminar stashes
```bash
git stash drop                # Eliminar último
git stash drop stash@{2}      # Eliminar específico
git stash clear               # Eliminar todos
```

---

## 🔍 Buscar y Ver Información

### Buscar en archivos
```bash
git grep "palabra"            # Buscar en archivos tracked
git grep -n "palabra"         # Con números de línea
git grep -c "palabra"         # Contar ocurrencias
```

### Ver archivos
```bash
git ls-files                  # Listar archivos tracked
git ls-files --others         # Archivos untracked
git ls-files --modified       # Archivos modificados
```

### Ver cambios en archivos
```bash
git show HEAD:archivo.txt     # Ver archivo en último commit
git show abc1234:archivo.txt  # Ver archivo en commit específico
git blame archivo.txt         # Ver quién modificó cada línea
```

---

## 🧹 Limpieza

### Limpiar archivos no tracked
```bash
git clean -n                  # Dry run (ver qué se eliminará)
git clean -f                  # Eliminar archivos
git clean -fd                 # Eliminar archivos y directorios
git clean -fX                 # Eliminar solo archivos ignorados
```

### Optimizar repositorio
```bash
git gc                        # Garbage collection
git prune                     # Eliminar objetos inalcanzables
```

---

## 🔧 Solución de Problemas Comunes

### HEAD desacoplado (detached HEAD)
```bash
git checkout main             # Volver a rama
git checkout -b nueva-rama    # Crear rama desde HEAD actual
```

### Conflictos de merge
```bash
git status                    # Ver archivos en conflicto
# Editar archivos manualmente
git add archivo-resuelto.txt
git commit                    # Completar merge
# O abortar:
git merge --abort
```

### Recuperar commits perdidos
```bash
git reflog                    # Ver historial de referencias
git checkout abc1234          # Ir a commit perdido
git cherry-pick abc1234       # Aplicar commit perdido
```

### Cambiar URL del remoto
```bash
git remote set-url origin https://nueva-url.git
git remote -v                 # Verificar
```

### Eliminar archivos del historial
```bash
git rm --cached archivo.txt   # Dejar de trackear (mantiene archivo)
git rm archivo.txt            # Eliminar archivo
```

---

## 🔐 Autenticación

### Guardar credenciales
```bash
git config --global credential.helper store   # Guardar permanentemente
git config --global credential.helper cache   # Guardar temporalmente
git config --global credential.helper 'cache --timeout=3600'  # 1 hora
```

### Usar SSH en lugar de HTTPS
```bash
# Generar clave SSH
ssh-keygen -t ed25519 -C "tu@email.com"

# Cambiar URL a SSH
git remote set-url origin git@github.com:usuario/repo.git
```

---

## 📋 Workflows Comunes

### Workflow básico diario
```bash
git pull                      # Actualizar
# ... hacer cambios ...
git status                    # Ver cambios
git add .                     # Agregar cambios
git commit -m "mensaje"       # Commit
git push                      # Subir
```

### Crear feature branch
```bash
git checkout main
git pull
git checkout -b feature/nueva-funcionalidad
# ... trabajar ...
git add .
git commit -m "Agregar nueva funcionalidad"
git push -u origin feature/nueva-funcionalidad
```

### Actualizar feature branch con main
```bash
git checkout feature-branch
git fetch origin
git rebase origin/main
# O con merge:
git merge origin/main
```

### Corregir último commit
```bash
# Olvidaste agregar un archivo
git add archivo-olvidado.txt
git commit --amend --no-edit

# Cambiar mensaje
git commit --amend -m "Nuevo mensaje"
```

---

## 🆘 Comandos de Emergencia

### Deshacer TODO y volver a remoto
```bash
git fetch origin
git reset --hard origin/main
```

### Recuperar después de reset --hard
```bash
git reflog
git reset --hard HEAD@{1}     # Volver al estado anterior
```

### Eliminar cambios locales y actualizar
```bash
git fetch --all
git reset --hard origin/main
git clean -fd
```

---

## 📝 Aliases Útiles

Agregar al archivo `~/.gitconfig`:

```bash
[alias]
    st = status
    co = checkout
    br = branch
    ci = commit
    unstage = restore --staged
    last = log -1 HEAD
    visual = log --graph --oneline --all
    undo = reset --soft HEAD~1
    amend = commit --amend --no-edit
```

Usar aliases:
```bash
git st           # En lugar de git status
git co main      # En lugar de git checkout main
git visual       # Ver gráfico de commits
```

---

## 🎯 Mejores Prácticas

1. **Commits frecuentes y pequeños** - Mejor muchos commits pequeños que uno grande
2. **Mensajes descriptivos** - "Agregar validación de email" en lugar de "fix"
3. **Pull antes de push** - Siempre actualiza antes de subir cambios
4. **No hacer force push en ramas compartidas** - Solo en tus ramas personales
5. **Usar branches** - main/master solo para código estable
6. **Revisar antes de commit** - Usa `git diff` y `git status`
7. **No commitear archivos sensibles** - Usa `.gitignore` para .env, credenciales, etc.

---

## 🔗 Referencias Rápidas

- Estado del repositorio: `git status`
- Ver cambios: `git diff`
- Agregar archivos: `git add .`
- Hacer commit: `git commit -m "mensaje"`
- Subir cambios: `git push`
- Descargar cambios: `git pull`
- Deshacer commit: `git reset --soft HEAD~1`
- Ver historial: `git log --oneline`
- Crear rama: `git checkout -b nombre`
- Cambiar rama: `git checkout nombre`

---

**💡 Tip**: Usa `git --help` o `git <comando> --help` para ver la documentación completa de cualquier comando.
