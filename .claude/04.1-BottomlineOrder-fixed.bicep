param logicAppState string
param environment string 
param workflowNames object

param businessCentral object
param storageAccount object 

#disable-next-line no-unused-params
param systemReferences object = {}
#disable-next-line no-unused-params
param dataverse object

var prefix = 'la-${environment}-bc'
var nameOfLogicApp string = '${prefix}-bottomline-order'

var connections object = {
  businessCentral: {
    id: '/subscriptions/${subscription().subscriptionId}/providers/Microsoft.Web/locations/${resourceGroup().location}/managedApis/dynamicssmbsaas'
    connectionId: resourceId('Microsoft.Web/connections', 'dynamicssmbsaas')
  }

  azureBlob: {
    id: '/subscriptions/${subscription().subscriptionId}/providers/Microsoft.Web/locations/${resourceGroup().location}/managedApis/azureblob'
    connectionId: resourceId('Microsoft.Web/connections', 'azureblob')
  }
}

var childFlows object = {
    GetErrorMessage: resourceId('Microsoft.Logic/workflows', '${prefix}-${workflowNames.helperGetErrorMessage}')
    SendNotification: resourceId('Microsoft.Logic/workflows', '${prefix}-${workflowNames.helperSendNotification}')
    ThrowError: resourceId('Microsoft.Logic/workflows', '${prefix}-${workflowNames.helperThrowError}')
}

var norwayConfig = businessCentral.countries[indexOf(map(businessCentral.countries, c => c.name), 'norway')]
var swedenConfig = businessCentral.countries[indexOf(map(businessCentral.countries, c => c.name), 'sweden')]

resource resource 'Microsoft.Logic/workflows@2019-05-01' = {
  name: nameOfLogicApp
  location: resourceGroup().location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    state: logicAppState
    definition: {
      '$schema': 'https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#'
      contentVersion: '1.0.0.0'
      parameters: {}
      triggers: {
        Recurrence: {
          recurrence: {
            frequency: 'Minute'
            interval: 15
          }
          evaluatedRecurrence: {
            frequency: 'Minute'
            interval: 15
          }
          type: 'Recurrence'
        }
      }
      actions: {
        Try: {
          type: 'Scope'
          actions: {
            Initialize_Norway_Orders_Variable: {
              type: 'InitializeVariable'
              inputs: {
                variables: [
                  {
                    name: 'norwayOrders'
                    type: 'array'
                    value: []
                  }
                ]
              }
            }
            Initialize_Sweden_Orders_Variable: {
              type: 'InitializeVariable'
              inputs: {
                variables: [
                  {
                    name: 'swedenOrders'
                    type: 'array'
                    value: []
                  }
                ]
              }
              runAfter: {
                Initialize_Norway_Orders_Variable: ['Succeeded']
              }
            }
            Get_Norway_Orders: {
              type: 'Http'
              inputs: {
                method: 'GET'
                uri: 'https://api.businesscentral.dynamics.com/v2.0/${businessCentral.environmentName}/api/${businessCentral.apiCategories.bottomline}/companies(${norwayConfig.companyId})/salesOrders?$filter=readyForBottomline%20eq%20true&$top=1'
                authentication: {
                  type: 'Raw'
                  value: '@{connectionRuntimeUrl(\'@parameters(\'\'$connections\'\')[\'\'businessCentral\'\'][\'\'connectionId\'\']\')'
                }
              }
              runAfter: {
                Initialize_Sweden_Orders_Variable: ['Succeeded']
              }
            }
            Condition_Norway_Orders_Available: {
              type: 'If'
              expression: {
                and: [
                  {
                    greater: [
                      '@length(body(\'Get_Norway_Orders\')?[\'value\'])'
                      0
                    ]
                  }
                ]
              }
              actions: {
                Set_Norway_Orders: {
                  type: 'SetVariable'
                  inputs: {
                    name: 'norwayOrders'
                    value: '@body(\'Get_Norway_Orders\')?[\'value\']'
                  }
                }
                Process_Norway_Order: {
                  type: 'Foreach'
                  foreach: '@variables(\'norwayOrders\')'
                  actions: {
                    Create_Blob_For_Norway_Order: {
                      type: 'ApiConnection'
                      inputs: {
                        host: {
                          connection: {
                            name: '@parameters(\'$connections\')[\'azureBlob\'][\'connectionId\']'
                          }
                        }
                        method: 'post'
                        path: '/v2/datasets/@{encodeURIComponent(encodeURIComponent(\'${storageAccount.containerName}\'))}/files'
                        queries: {
                          folderPath: '/${storageAccount.bottomlinePath}/orders'
                          name: 'norway-order-@{items(\'Process_Norway_Order\')?[\'number\']}-@{utcNow()}.json'
                          queryParametersSingleEncoded: true
                        }
                        body: '@items(\'Process_Norway_Order\')'
                      }
                    }
                    Mark_Norway_Order_As_Sent: {
                      type: 'Http'
                      inputs: {
                        method: 'PATCH'
                        uri: 'https://api.businesscentral.dynamics.com/v2.0/${businessCentral.environmentName}/api/${businessCentral.apiCategories.bottomline}/companies(${norwayConfig.companyId})/salesOrders(@{items(\'Process_Norway_Order\')?[\'systemId\']})'
                        headers: {
                          'Content-Type': 'application/json'
                          'If-Match': '@items(\'Process_Norway_Order\')?[\'@odata.etag\']'
                        }
                        body: {
                          sentToBottomline: true
                        }
                        authentication: {
                          type: 'Raw'
                          value: '@{connectionRuntimeUrl(\'@parameters(\'\'$connections\'\')[\'\'businessCentral\'\'][\'\'connectionId\'\']\')'
                        }
                      }
                      runAfter: {
                        Create_Blob_For_Norway_Order: ['Succeeded']
                      }
                    }
                  }
                  runAfter: {
                    Set_Norway_Orders: ['Succeeded']
                  }
                }
              }
              else: {
                actions: {
                  Get_Sweden_Orders: {
                    type: 'Http'
                    inputs: {
                      method: 'GET'
                      uri: 'https://api.businesscentral.dynamics.com/v2.0/${businessCentral.environmentName}/api/${businessCentral.apiCategories.bottomline}/companies(${swedenConfig.companyId})/salesOrders?$filter=readyForBottomline%20eq%20true&$top=1'
                      authentication: {
                        type: 'Raw'
                        value: '@{connectionRuntimeUrl(\'@parameters(\'\'$connections\'\')[\'\'businessCentral\'\'][\'\'connectionId\'\']\')'
                      }
                    }
                  }
                  Condition_Sweden_Orders_Available: {
                    type: 'If'
                    expression: {
                      and: [
                        {
                          greater: [
                            '@length(body(\'Get_Sweden_Orders\')?[\'value\'])'
                            0
                          ]
                        }
                      ]
                    }
                    actions: {
                      Set_Sweden_Orders: {
                        type: 'SetVariable'
                        inputs: {
                          name: 'swedenOrders'
                          value: '@body(\'Get_Sweden_Orders\')?[\'value\']'
                        }
                      }
                      Process_Sweden_Order: {
                        type: 'Foreach'
                        foreach: '@variables(\'swedenOrders\')'
                        actions: {
                          Create_Blob_For_Sweden_Order: {
                            type: 'ApiConnection'
                            inputs: {
                              host: {
                                connection: {
                                  name: '@parameters(\'$connections\')[\'azureBlob\'][\'connectionId\']'
                                }
                              }
                              method: 'post'
                              path: '/v2/datasets/@{encodeURIComponent(encodeURIComponent(\'${storageAccount.containerName}\'))}/files'
                              queries: {
                                folderPath: '/${storageAccount.bottomlinePath}/orders'
                                name: 'sweden-order-@{items(\'Process_Sweden_Order\')?[\'number\']}-@{utcNow()}.json'
                                queryParametersSingleEncoded: true
                              }
                              body: '@items(\'Process_Sweden_Order\')'
                            }
                          }
                          Mark_Sweden_Order_As_Sent: {
                            type: 'Http'
                            inputs: {
                              method: 'PATCH'
                              uri: 'https://api.businesscentral.dynamics.com/v2.0/${businessCentral.environmentName}/api/${businessCentral.apiCategories.bottomline}/companies(${swedenConfig.companyId})/salesOrders(@{items(\'Process_Sweden_Order\')?[\'systemId\']})'
                              headers: {
                                'Content-Type': 'application/json'
                                'If-Match': '@items(\'Process_Sweden_Order\')?[\'@odata.etag\']'
                              }
                              body: {
                                sentToBottomline: true
                              }
                              authentication: {
                                type: 'Raw'
                                value: '@{connectionRuntimeUrl(\'@parameters(\'\'$connections\'\')[\'\'businessCentral\'\'][\'\'connectionId\'\']\')'
                              }
                            }
                            runAfter: {
                              Create_Blob_For_Sweden_Order: ['Succeeded']
                            }
                          }
                        }
                        runAfter: {
                          Set_Sweden_Orders: ['Succeeded']
                        }
                      }
                    }
                    runAfter: {
                      Get_Sweden_Orders: ['Succeeded']
                    }
                  }
                }
              }
              runAfter: {
                Get_Norway_Orders: ['Succeeded']
              }
            }
          }
        }
        Catch: {
          type: 'Scope'
          actions: {
            Get_Error_Message: {
              type: 'Workflow'
              inputs: {
                host: {
                  triggerName: 'manual'
                  workflow: {
                    id: childFlows.GetErrorMessage
                  }
                }
                body: {
                  errorObject: '@result(\'Try\')'
                  source: 'Bottomline Order Handler'
                }
              }
            }
            Send_Error_Notification: {
              type: 'Workflow'
              inputs: {
                host: {
                  triggerName: 'manual'
                  workflow: {
                    id: childFlows.SendNotification
                  }
                }
                body: {
                  message: '@body(\'Get_Error_Message\')?[\'errorMessage\']'
                  source: 'Bottomline Order Handler'
                  severity: 'Error'
                }
              }
              runAfter: {
                Get_Error_Message: ['Succeeded']
              }
            }
          }
          runAfter: {
            Try: ['Failed', 'Skipped', 'TimedOut']
          }
        }
        Finally: {
          type: 'Scope'
          actions: {
            Response: {
              type: 'Response'
              kind: 'Http'
              inputs: {
                statusCode: 200
                body: {
                  message: 'Bottomline order processing completed'
                  timestamp: '@utcNow()'
                }
              }
            }
          }
          runAfter: {
            Try: ['Succeeded']
            Catch: ['Succeeded', 'Failed', 'Skipped', 'TimedOut']
          }
        }
      }
    }
    parameters: {
      '$connections': {
        value: connections
      }
    }
  }
}

output logicAppName string = nameOfLogicApp