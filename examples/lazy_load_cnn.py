from pyspark.sql import SparkSession
from pyspark.ml.feature import VectorAssembler
from sparktorch import SparkTorch, serialize_torch_obj_lazy
from pyspark.sql.functions import rand
from pyspark.ml.evaluation import MulticlassClassificationEvaluator
from pyspark.ml.pipeline import Pipeline
from examples.cnn_network import Net
import torch
import torch.nn as nn


if __name__ == '__main__':
    spark = SparkSession.builder \
        .appName("examples") \
        .master('local[2]').config('spark.driver.memory', '2g') \
        .getOrCreate()

    # Read in mnist_train.csv dataset
    df = spark.read.option("inferSchema", "true").csv('examples/mnist_train.csv').orderBy(rand()).repartition(2)

    # Build the pytorch object
    torch_obj = serialize_torch_obj_lazy(
        model=Net,
        criterion=nn.CrossEntropyLoss,
        optimizer=torch.optim.Adam,
        optimizer_params={'lr': 0.0003}
    )

    # Setup features
    vector_assembler = VectorAssembler(inputCols=df.columns[1:785], outputCol='features')

    # Demonstration of some options. Not all are required
    # Note: This uses the barrier execution mode, which is sensitive to the number of partitions
    spark_model = SparkTorch(
        inputCol='features',
        labelCol='_c0',
        predictionCol='predictions',
        torchObj=torch_obj,
        iters=100,
        verbose=1,
        miniBatch=128,
        earlyStopPatience=20,
        validationPct=0.2
    )

    # Create and save the Pipeline
    p = Pipeline(stages=[vector_assembler, spark_model]).fit(df)

    # Run predictions and evaluation
    predictions = p.transform(df).persist()
    evaluator = MulticlassClassificationEvaluator(
        labelCol="_c0", predictionCol="predictions", metricName="accuracy")

    accuracy = evaluator.evaluate(predictions)
    print("Train accuracy = %g" % accuracy)

