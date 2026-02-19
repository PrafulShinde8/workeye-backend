#!/bin/bash
# cleanup_and_setup.sh
# Run this on Render to completely remove psycopg2 and install psycopg3

echo "========================================"
echo "🔧 CLEANING UP PSYCOPG2 COMPLETELY"
echo "========================================"

# Uninstall ALL versions of psycopg2
pip uninstall -y psycopg2 psycopg2-binary 2>/dev/null
echo "✅ Removed psycopg2 and psycopg2-binary"

# Clear pip cache
pip cache purge 2>/dev/null
echo "✅ Cleared pip cache"

# Install ONLY psycopg version 3
pip install --force-reinstall psycopg[binary]==3.1.18
echo "✅ Installed psycopg[binary]==3.1.18"

# Verify installation
python -c "import psycopg; print('✅ psycopg version:', psycopg.__version__)"

echo ""
echo "========================================"
echo "✅ CLEANUP COMPLETE!"
echo "========================================"
echo ""
echo "Now you can run: python init_db.py"
echo ""
