# patient_360 Spark Thrift Server image (LLD §9.1.1, §13 Decision 12).
# Runs the Spark Thrift Server (HiveServer2 on :10000) — the Spark SQL
# endpoint Liquibase targets to execute Delta DDL
# (`CREATE TABLE unity.<schema>.<table> ... USING DELTA LOCATION '...'`)
# so UC EXTERNAL Delta tables are pre-created before any pipeline write.
#
# Bundles: JDK 17 + Apache Spark 4.1.0 (Scala 2.13) + Delta + Unity Catalog
# jars. Versions match the pins in inputs/code/v1/LIBRARIES.md:
#   io.delta:delta-spark_2.13:4.3.0
#   io.unitycatalog:unitycatalog-spark_4.1_2.13:0.5.0
FROM apache/spark:4.1.1-scala2.13-java17-python3-ubuntu

USER root

# --------------------------------------------------------------------------
# AC11 — Delta + Unity Catalog jars are resolved at BUILD time INTO Spark's
# classpath directory /opt/spark/jars/ (as root, before switching to
# USER spark). The Thrift Server then starts with NO network access and NO
# ivy resolution at runtime.
#
# Runtime ivy/package resolution is impossible here: the `spark` user's
# HOME=/nonexistent cannot write the ivy cache, so a runtime `--packages`
# (or a package-coordinate line in spark-defaults.conf) fails with
#   java.io.FileNotFoundException: /nonexistent/.ivy2/...
# We therefore drive ivy ONCE at build time (root HOME is writable), then
# copy the full resolved transitive closure into /opt/spark/jars/.
# --------------------------------------------------------------------------
ARG DELTA_VERSION=4.3.0
ARG UC_SPARK_VERSION=0.5.0
RUN set -eux; \
    IVY_DIR=/tmp/ivy-build; \
    mkdir -p "$IVY_DIR"; \
    # Resolve the full transitive closure of the Delta + UC Spark connectors
    # into a throwaway ivy dir (build-time network is available).
    # NOTE: `--version` does NOT resolve --packages; run a real (throwaway)
    # job so ivy actually downloads the transitive closure into ${IVY_DIR}/jars.
    /opt/spark/bin/spark-submit \
        --packages "io.delta:delta-spark_2.13:${DELTA_VERSION},io.unitycatalog:unitycatalog-spark_4.1_2.13:${UC_SPARK_VERSION}" \
        --conf "spark.jars.ivy=${IVY_DIR}" \
        --class org.apache.spark.examples.SparkPi \
        /opt/spark/examples/jars/spark-examples_2.13-4.1.1.jar 1 >/dev/null 2>&1 || true; \
    # Copy every resolved jar into Spark's classpath dir so they are on the
    # classpath at runtime with NO ivy / network dependency.
    find "$IVY_DIR/jars" -name '*.jar' -exec cp -n {} /opt/spark/jars/ \; ; \
    # Sanity: the two connector jars must have landed in /opt/spark/jars/.
    ls /opt/spark/jars/ | grep -E 'delta-spark_2.13-' ; \
    ls /opt/spark/jars/ | grep -E 'unitycatalog-spark_4.1_2.13-' ; \
    rm -rf "$IVY_DIR"

# Unity Catalog wired as a named side catalog (LLD §13 Decision 12):
#   spark_catalog -> DeltaCatalog; unity -> UCSingleCatalog; defaultCatalog=unity.
# The Thrift Server inherits these via spark-defaults.conf.
#
# AC11: spark-defaults.conf MUST NOT contain a runtime package-coordinate
# line — the jars are already on the classpath (baked into /opt/spark/jars/
# above), and runtime package resolution would fail (HOME=/nonexistent ivy
# cache). Only the catalog/extension wiring lives here.
COPY <<'EOF' /opt/spark/conf/spark-defaults.conf
spark.sql.extensions                                io.delta.sql.DeltaSparkSessionExtension
spark.sql.catalog.spark_catalog                     org.apache.spark.sql.delta.catalog.DeltaCatalog
spark.sql.catalog.unity                             io.unitycatalog.spark.UCSingleCatalog
spark.sql.catalog.unity.uri                         http://unity-catalog:8080
spark.sql.catalog.unity.token                       ${env:UC_TOKEN}
spark.sql.defaultCatalog                            unity
EOF

USER spark
EXPOSE 10000

# Launch the Spark Thrift Server in the FOREGROUND (HiveServer2 on :10000).
# `start-thriftserver.sh` daemonizes and returns, which would exit the
# container; invoke the HiveThriftServer2 driver class directly via
# spark-submit so PID 1 stays alive under the Spark process.
ENTRYPOINT ["/opt/spark/bin/spark-submit", \
            "--master", "local[2]", \
            "--class", "org.apache.spark.sql.hive.thriftserver.HiveThriftServer2", \
            "--name", "patient_360-thrift", \
            "--conf", "spark.sql.hive.thriftServer.singleSession=true", \
            "--hiveconf", "hive.server2.thrift.port=10000", \
            "--hiveconf", "hive.server2.thrift.bind.host=0.0.0.0", \
            "spark-internal"]
